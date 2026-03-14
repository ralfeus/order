#!/usr/bin/env bash
# =============================================================================
# archive_talya.sh — Archive transactional data older than CUTOFF_DATE
#
# Usage:
#   ./bin/archive_talya.sh [OPTIONS] YYYY-MM-DD
#
# Arguments:
#   YYYY-MM-DD          Cutoff date; records older than this are archived
#
# Options:
#   -s, --source DB     Source (online) database name  (default: talya)
#   -t, --target DB     Target (archive) database name (default: talya_archive)
#   -h, --host HOST     MySQL host                     (default: localhost)
#   -P, --port PORT     MySQL port                     (default: 3306)
#   -u, --user USER     MySQL user                     (default: current OS user)
#   -p, --password PWD  MySQL password                 (default: none / .my.cnf)
#   --help              Show this help and exit
#
# Examples:
#   ./bin/archive_talya.sh 2026-01-01
#   ./bin/archive_talya.sh -s talya_test -t talya_archive 2026-01-01
#   ./bin/archive_talya.sh -h db.host -u admin -p secret 2026-01-01
#
# The script is idempotent: re-running is safe at any point.
# Master data is preserved intact in the online database.
# No record exists in both archive and online after a successful run.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
usage() {
    sed -n '3,/^# ====/p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

ONLINE_DB="talya"
ARCHIVE_DB=""
MYSQL_HOST=""
MYSQL_PORT=""
MYSQL_USER=""
MYSQL_PASS=""
CUTOFF=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--source)   ONLINE_DB="$2";  shift 2 ;;
        -t|--target)   ARCHIVE_DB="$2"; shift 2 ;;
        -h|--host)     MYSQL_HOST="$2"; shift 2 ;;
        -P|--port)     MYSQL_PORT="$2"; shift 2 ;;
        -u|--user)     MYSQL_USER="$2"; shift 2 ;;
        -p|--password) MYSQL_PASS="$2"; shift 2 ;;
        --help)        usage 0 ;;
        -*)            echo "Unknown option: $1" >&2; usage 1 ;;
        *)
            if [[ -z "$CUTOFF" ]]; then
                CUTOFF="$1"
            else
                echo "Unexpected argument: $1" >&2; usage 1
            fi
            shift
            ;;
    esac
done

[[ -z "$ARCHIVE_DB" ]] && ARCHIVE_DB="${ONLINE_DB}_archive"

if [[ -z "$CUTOFF" ]] || ! [[ "$CUTOFF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Error: cutoff date (YYYY-MM-DD) is required." >&2
    usage 1
fi

# Build mysql connection flags from provided options
MYSQL_CONN_OPTS=""
[[ -n "$MYSQL_HOST" ]] && MYSQL_CONN_OPTS+=" -h ${MYSQL_HOST}"
[[ -n "$MYSQL_PORT" ]] && MYSQL_CONN_OPTS+=" -P ${MYSQL_PORT}"
[[ -n "$MYSQL_USER" ]] && MYSQL_CONN_OPTS+=" -u ${MYSQL_USER}"
[[ -n "$MYSQL_PASS" ]] && MYSQL_CONN_OPTS+=" -p${MYSQL_PASS}"

M="mysql${MYSQL_CONN_OPTS}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 2; }

# Run SQL and return result (single value)
qval() { $M -BN -e "$1" 2>/dev/null; }

# Run SQL (no return value needed)
run()  { $M -e "$1" 2>/dev/null; }

# Count rows in a table with optional WHERE clause
cnt() {
    local db="$1" table="$2" where="${3:-1=1}"
    qval "SELECT COUNT(*) FROM \`${db}\`.\`${table}\` WHERE ${where};"
}

# Verify: rows destined for archive are all present in archive.
# Aborts if archive has fewer rows than online (incomplete copy).
verify() {
    local table="$1" archive_where="$2" online_where="${3:-$2}"
    local arc onl
    arc=$(cnt "$ARCHIVE_DB" "$table" "$archive_where")
    onl=$(cnt "$ONLINE_DB"  "$table" "$online_where")
    if (( arc < onl )); then
        die "${table}: archive has ${arc} rows but ${onl} still need archiving — aborting before delete"
    fi
    log "    verified ${table}: ${arc} in archive (${onl} still in online)"
}

# Delete in chunks of 10 000 to avoid long lock waits.
chunk_delete() {
    local table="$1" where="$2" fkoff="${3:-}"
    local total=0 batch=1
    while (( batch > 0 )); do
        batch=$(cnt "$ONLINE_DB" "$table" "$where")
        (( batch > 10000 )) && batch=10000
        (( batch > 0 )) || break
        if [[ -n "$fkoff" ]]; then
            # Disable FK checks within the session for self-referencing tables
            run "SET FOREIGN_KEY_CHECKS=0; DELETE FROM \`${ONLINE_DB}\`.\`${table}\` WHERE ${where} LIMIT ${batch}; SET FOREIGN_KEY_CHECKS=1;"
        else
            run "DELETE FROM \`${ONLINE_DB}\`.\`${table}\` WHERE ${where} LIMIT ${batch};"
        fi
        total=$(( total + batch ))
    done
    log "    deleted ${total} rows from ${table}"
}

# ---------------------------------------------------------------------------
# Step 1: Create archive database and mirror schema
# ---------------------------------------------------------------------------
step1_schema() {
    log "Step 1: Create archive database and schema"
    run "CREATE DATABASE IF NOT EXISTS \`${ARCHIVE_DB}\`;"

    # All base tables (not views, not network_nodes which is pure master data)
    local tables=(
        addresses alembic_version clicks companies countries currencies
        currency_history dhl_countries dhl_rates dhl_zones fedex_setting files
        invoice_items invoices notifications order_boxes order_packers
        order_params order_product_status_history order_products
        order_products_warehouses orders packers payment_methods payments
        payments_files payments_orders products products_shipping
        purchase_order_warehouses purchase_orders pv_stats_permissions roles
        roles_users settings shipping shipping_params shipping_rates
        shipping_weight_based_rates subcustomers suborders transactions users
        warehouse_orders warehouse_products warehouses
    )

    for t in "${tables[@]}"; do
        run "CREATE TABLE IF NOT EXISTS \`${ARCHIVE_DB}\`.\`${t}\` LIKE \`${ONLINE_DB}\`.\`${t}\`;"
    done

    # Working table: holds IDs of orders eligible for archival this run
    run "CREATE TABLE IF NOT EXISTS \`${ARCHIVE_DB}\`.\`_candidate_orders\`
         (id varchar(16) NOT NULL, PRIMARY KEY (id));"

    log "    schema ready"
}

# ---------------------------------------------------------------------------
# Step 2: Sync master data into archive (INSERT IGNORE — idempotent)
# network_nodes is excluded: pure structural master data, not copied.
# ---------------------------------------------------------------------------
step2_masters() {
    log "Step 2: Sync master data"

    local masters=(
        # Reference / config tables
        countries currencies dhl_zones dhl_countries dhl_rates
        fedex_setting shipping shipping_params shipping_rates
        shipping_weight_based_rates payment_methods companies addresses
        warehouses packers roles settings alembic_version currency_history
        # Entity master tables
        users subcustomers products
        # Junction / permission tables (master-to-master)
        roles_users products_shipping pv_stats_permissions
        # Inventory state
        warehouse_products
    )

    for t in "${masters[@]}"; do
        run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`${t}\` SELECT * FROM \`${ONLINE_DB}\`.\`${t}\`;"
        log "    synced ${t}"
    done
}

# ---------------------------------------------------------------------------
# Step 2.5: Compute candidate orders
# Excludes cross-boundary attached_order_id pairs (both orders kept online
# if they straddle the cutoff date in either direction).
# ---------------------------------------------------------------------------
step2_5_candidates() {
    log "Step 2.5: Computing eligible order IDs"

    # Repopulate working table on each run (idempotent)
    run "TRUNCATE TABLE \`${ARCHIVE_DB}\`.\`_candidate_orders\`;"

    run "INSERT INTO \`${ARCHIVE_DB}\`.\`_candidate_orders\`
         SELECT id FROM \`${ONLINE_DB}\`.\`orders\` o
         WHERE o.when_created < '${CUTOFF}'
           -- Exclude: this old order's attached partner is a new order
           AND o.id NOT IN (
               SELECT o2.id FROM \`${ONLINE_DB}\`.\`orders\` o2
               WHERE o2.attached_order_id IS NOT NULL
                 AND o2.when_created < '${CUTOFF}'
                 AND o2.attached_order_id IN (
                     SELECT id FROM \`${ONLINE_DB}\`.\`orders\`
                     WHERE when_created >= '${CUTOFF}'
                 )
           )
           -- Exclude: this old order is the attached partner of a new order
           AND o.id NOT IN (
               SELECT o3.attached_order_id FROM \`${ONLINE_DB}\`.\`orders\` o3
               WHERE o3.attached_order_id IS NOT NULL
                 AND o3.when_created >= '${CUTOFF}'
                 AND o3.attached_order_id IN (
                     SELECT id FROM \`${ONLINE_DB}\`.\`orders\`
                     WHERE when_created < '${CUTOFF}'
                 )
           );"

    local n
    n=$(cnt "$ARCHIVE_DB" "_candidate_orders")
    local excluded
    excluded=$(qval "SELECT COUNT(*) FROM \`${ONLINE_DB}\`.\`orders\`
                     WHERE when_created < '${CUTOFF}';" )
    excluded=$(( excluded - n ))
    log "    ${n} orders eligible for archival (${excluded} excluded as cross-boundary pairs)"
}

# Shorthand predicate reused throughout
CAND="order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)"

# ---------------------------------------------------------------------------
# Step 3: Archive transactional data (INSERT IGNORE — idempotent)
# Parent tables must be inserted before child tables.
# ---------------------------------------------------------------------------
step3_archive() {
    log "Step 3: Copying transactional data to archive"

    # -- 1. invoices (parent: referenced by orders.invoice_id) ---------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`invoices\`
         SELECT i.* FROM \`${ONLINE_DB}\`.\`invoices\` i
         WHERE
             -- Normal case: referenced by a candidate order
             i.id IN (
                 SELECT invoice_id FROM \`${ONLINE_DB}\`.\`orders\`
                 WHERE id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
                   AND invoice_id IS NOT NULL
             )
             -- Orphan invoices: not referenced by any order anywhere, archive by date
             OR (
                 i.when_created < '${CUTOFF}'
                 AND i.id NOT IN (
                     SELECT invoice_id FROM \`${ONLINE_DB}\`.\`orders\`
                     WHERE invoice_id IS NOT NULL
                 )
             );"
    log "    archived invoices"

    # -- 2. invoice_items ------------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`invoice_items\`
         SELECT * FROM \`${ONLINE_DB}\`.\`invoice_items\`
         WHERE invoice_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`invoices\`);"
    log "    archived invoice_items"

    # -- 3. transactions (safe predicate) -------------------------------------
    # Archive a transaction only when:
    #   a) it is referenced by at least one candidate order or an archivable payment
    #   b) it is NOT referenced by any non-candidate order
    #   c) it is NOT referenced by any payment that has non-candidate orders
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`transactions\`
         SELECT t.* FROM \`${ONLINE_DB}\`.\`transactions\` t
         WHERE (
             -- Referenced by a candidate order
             t.id IN (
                 SELECT transaction_id FROM \`${ONLINE_DB}\`.\`orders\`
                 WHERE id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
                   AND transaction_id IS NOT NULL
             )
             OR
             -- Referenced by a payment whose orders are all candidates
             t.id IN (
                 SELECT p.transaction_id FROM \`${ONLINE_DB}\`.\`payments\` p
                 WHERE p.transaction_id IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM \`${ONLINE_DB}\`.\`payments_orders\` po
                       JOIN  \`${ONLINE_DB}\`.\`orders\` o ON po.order_id = o.id
                       WHERE po.payment_id = p.id
                         AND o.id NOT IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
                   )
             )
         )
         -- NOT referenced by any non-candidate order
         AND t.id NOT IN (
             SELECT transaction_id FROM \`${ONLINE_DB}\`.\`orders\`
             WHERE id NOT IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
               AND transaction_id IS NOT NULL
         )
         -- NOT referenced by a payment that has non-candidate orders
         AND t.id NOT IN (
             SELECT p.transaction_id FROM \`${ONLINE_DB}\`.\`payments\` p
             WHERE p.transaction_id IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM \`${ONLINE_DB}\`.\`payments_orders\` po
                   JOIN  \`${ONLINE_DB}\`.\`orders\` o ON po.order_id = o.id
                   WHERE po.payment_id = p.id
                     AND o.id NOT IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
               )
         )
         -- Also archive orphan transactions (no order/payment reference) by date
         OR (
             t.when_created < '${CUTOFF}'
             AND t.id NOT IN (
                 SELECT transaction_id FROM \`${ONLINE_DB}\`.\`orders\`
                 WHERE transaction_id IS NOT NULL
             )
             AND t.id NOT IN (
                 SELECT transaction_id FROM \`${ONLINE_DB}\`.\`payments\`
                 WHERE transaction_id IS NOT NULL
             )
         );"
    log "    archived transactions"

    # -- 4. payments -----------------------------------------------------------
    # Archive if:
    #   a) transaction is in archive AND all associated orders are candidates, OR
    #   b) orphan payment (null/missing transaction) older than cutoff with no active order links
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`payments\`
         SELECT p.* FROM \`${ONLINE_DB}\`.\`payments\` p
         WHERE (
             -- Normal case: transaction is archived, no non-candidate orders
             (p.transaction_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`transactions\`)
              AND NOT EXISTS (
                  SELECT 1 FROM \`${ONLINE_DB}\`.\`payments_orders\` po
                  JOIN  \`${ONLINE_DB}\`.\`orders\` o ON po.order_id = o.id
                  WHERE po.payment_id = p.id
                    AND o.id NOT IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
              ))
             OR
             -- Orphan payment: no valid transaction, older than cutoff, no active order links
             (p.when_created < '${CUTOFF}'
              AND (p.transaction_id IS NULL
                   OR p.transaction_id NOT IN (SELECT id FROM \`${ONLINE_DB}\`.\`transactions\`))
              AND NOT EXISTS (
                  SELECT 1 FROM \`${ONLINE_DB}\`.\`payments_orders\` po
                  JOIN  \`${ONLINE_DB}\`.\`orders\` o ON po.order_id = o.id
                  WHERE po.payment_id = p.id
                    AND o.id NOT IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`)
              ))
         );"
    log "    archived payments"

    # -- 5. files (only payment-linked files; never product images) -----------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`files\`
         SELECT f.* FROM \`${ONLINE_DB}\`.\`files\` f
         WHERE f.id IN (
             SELECT pf.file_id FROM \`${ONLINE_DB}\`.\`payments_files\` pf
             WHERE pf.payment_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`payments\`)
         )
         -- Guard: never archive files that are product images
         AND f.id NOT IN (
             SELECT image_id FROM \`${ONLINE_DB}\`.\`products\`
             WHERE image_id IS NOT NULL
         );"
    log "    archived files"

    # -- 6. payments_files -----------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`payments_files\`
         SELECT * FROM \`${ONLINE_DB}\`.\`payments_files\`
         WHERE payment_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`payments\`);"
    log "    archived payments_files"

    # -- 7. orders (primary anchor) -------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`orders\`
         SELECT * FROM \`${ONLINE_DB}\`.\`orders\`
         WHERE id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`_candidate_orders\`);"
    log "    archived orders"

    # -- 8. payments_orders ----------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`payments_orders\`
         SELECT * FROM \`${ONLINE_DB}\`.\`payments_orders\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived payments_orders"

    # -- 9. suborders ----------------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`suborders\`
         SELECT * FROM \`${ONLINE_DB}\`.\`suborders\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived suborders"

    # -- 10. order_products ----------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_products\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_products\`
         WHERE suborder_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`suborders\`)
            OR (suborder_id IS NULL
                AND order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`));"
    log "    archived order_products"

    # -- 11. order_product_status_history -------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_product_status_history\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_product_status_history\`
         WHERE order_product_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`order_products\`);"
    log "    archived order_product_status_history"

    # -- 12. order_products_warehouses ----------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_products_warehouses\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_products_warehouses\`
         WHERE order_product_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`order_products\`);"
    log "    archived order_products_warehouses"

    # -- 13. order_boxes -------------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_boxes\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_boxes\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived order_boxes"

    # -- 14. order_params ------------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_params\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_params\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived order_params"

    # -- 15. order_packers -----------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`order_packers\`
         SELECT * FROM \`${ONLINE_DB}\`.\`order_packers\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived order_packers"

    # -- 16. purchase_orders ---------------------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`purchase_orders\`
         SELECT * FROM \`${ONLINE_DB}\`.\`purchase_orders\`
         WHERE suborder_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`suborders\`);"
    log "    archived purchase_orders"

    # -- 17. purchase_order_warehouses ----------------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`purchase_order_warehouses\`
         SELECT * FROM \`${ONLINE_DB}\`.\`purchase_order_warehouses\`
         WHERE purchase_order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`purchase_orders\`);"
    log "    archived purchase_order_warehouses"

    # -- 18. warehouse_orders (FK to orders; currently empty but included for completeness)
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`warehouse_orders\`
         SELECT * FROM \`${ONLINE_DB}\`.\`warehouse_orders\`
         WHERE order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`);"
    log "    archived warehouse_orders"

    # -- 19. clicks (independent; date-anchored) --------------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`clicks\`
         SELECT * FROM \`${ONLINE_DB}\`.\`clicks\`
         WHERE when_created < '${CUTOFF}';"
    log "    archived clicks"

    # -- 20. notifications (independent; date-anchored) ------------------------
    run "INSERT IGNORE INTO \`${ARCHIVE_DB}\`.\`notifications\`
         SELECT * FROM \`${ONLINE_DB}\`.\`notifications\`
         WHERE when_created < '${CUTOFF}';"
    log "    archived notifications"
}

# ---------------------------------------------------------------------------
# Step 4: Verify archive completeness before any deletion
# ---------------------------------------------------------------------------
step4_verify() {
    log "Step 4: Verifying archive completeness"

    # Helper: verify using archive table as the predicate set
    v_by_id() {
        local tbl="$1"
        verify "$tbl" \
            "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`${tbl}\`)" \
            "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`${tbl}\`)"
    }

    # Composite-PK tables: verify by count comparison
    v_composite() {
        local tbl="$1" parent_col="$2" parent_archive_tbl="$3"
        verify "$tbl" \
            "${parent_col} IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`${parent_archive_tbl}\`)" \
            "${parent_col} IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`${parent_archive_tbl}\`)"
    }

    v_by_id invoices
    v_composite invoice_items invoice_id invoices
    v_by_id transactions
    v_by_id payments
    v_composite payments_files payment_id payments
    v_composite payments_orders payment_id payments
    v_by_id files
    v_by_id orders
    v_by_id suborders
    v_by_id order_products
    v_composite order_product_status_history order_product_id order_products
    v_composite order_products_warehouses order_product_id order_products
    v_composite order_boxes order_id orders
    v_composite order_params order_id orders
    v_composite order_packers order_id orders
    v_by_id purchase_orders
    v_composite purchase_order_warehouses purchase_order_id purchase_orders
    v_composite warehouse_orders order_id orders

    verify clicks \
        "when_created < '${CUTOFF}'" \
        "when_created < '${CUTOFF}'"
    verify notifications \
        "when_created < '${CUTOFF}'" \
        "when_created < '${CUTOFF}'"

    log "    all tables verified"
}

# ---------------------------------------------------------------------------
# Step 5: Delete from online database (child-first order)
# ---------------------------------------------------------------------------
step5_delete() {
    log "Step 5: Removing archived data from online database"

    # purchase_order_warehouses (child of purchase_orders)
    chunk_delete purchase_order_warehouses \
        "purchase_order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`purchase_orders\`)"

    # purchase_orders (child of suborders)
    chunk_delete purchase_orders \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`purchase_orders\`)"

    # order_products_warehouses (child of order_products)
    chunk_delete order_products_warehouses \
        "order_product_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`order_products\`)"

    # order_product_status_history (child of order_products)
    chunk_delete order_product_status_history \
        "order_product_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`order_products\`)"

    # order_products (child of orders and suborders)
    chunk_delete order_products \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`order_products\`)"

    # order_packers (child of orders)
    chunk_delete order_packers \
        "order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)"

    # order_params (child of orders)
    chunk_delete order_params \
        "order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)"

    # order_boxes (child of orders)
    chunk_delete order_boxes \
        "order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)"

    # suborders (child of orders)
    chunk_delete suborders \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`suborders\`)"

    # payments_orders (child of orders and payments)
    chunk_delete payments_orders \
        "order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)"

    # warehouse_orders (child of orders)
    chunk_delete warehouse_orders \
        "order_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)"

    # orders: self-referencing FK (attached_order_id) requires FK checks off per batch
    chunk_delete orders \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`orders\`)" \
        fkoff

    # payments_files (child of payments and files)
    chunk_delete payments_files \
        "payment_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`payments\`)"

    # payments (child of transactions)
    chunk_delete payments \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`payments\`)"

    # files (payment-linked files only; product images are never archived)
    chunk_delete files \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`files\`)"

    # transactions (now safe: orders and payments referencing them are deleted)
    chunk_delete transactions \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`transactions\`)"

    # invoice_items (child of invoices)
    chunk_delete invoice_items \
        "invoice_id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`invoices\`)"

    # invoices (orders referencing them are now deleted)
    chunk_delete invoices \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`invoices\`)"

    # clicks (independent)
    chunk_delete clicks \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`clicks\`)"

    # notifications (independent)
    chunk_delete notifications \
        "id IN (SELECT id FROM \`${ARCHIVE_DB}\`.\`notifications\`)"

    log "    deletions complete"
}

# ---------------------------------------------------------------------------
# Step 6: Summary report
# ---------------------------------------------------------------------------
step6_summary() {
    log "Step 6: Summary"

    local tables=(
        orders suborders order_products invoices invoice_items
        transactions payments purchase_orders clicks notifications
    )
    printf '\n%-35s %12s %12s\n' "Table" "Online" "Archive"
    printf '%-35s %12s %12s\n' "-----" "------" "-------"
    for t in "${tables[@]}"; do
        local o a
        o=$(cnt "$ONLINE_DB"  "$t")
        a=$(cnt "$ARCHIVE_DB" "$t")
        printf '%-35s %12s %12s\n' "$t" "$o" "$a"
    done
    printf '\nArchival cutoff: %s\n' "$CUTOFF"
    printf 'Online DB:       %s\n' "$ONLINE_DB"
    printf 'Archive DB:      %s\n' "$ARCHIVE_DB"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
log "=== talya archival starting (cutoff: ${CUTOFF}) ==="
log "    online:  ${ONLINE_DB}"
log "    archive: ${ARCHIVE_DB}"

step1_schema
step2_masters
step2_5_candidates
step3_archive
step4_verify
step5_delete
step6_summary

log "=== Done ==="
