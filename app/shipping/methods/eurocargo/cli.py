'''CLI commands for Eurocargo shipments'''
import logging

import click
from flask.cli import AppGroup

eurocargo_cli = AppGroup('eurocargo', help='Eurocargo shipment tools.')

URL_PARAM = 'eurocargo.shipment_url'
logger = logging.getLogger(__name__)


@eurocargo_cli.command('ship-invoice')
@click.argument('invoice_id')
@click.option('--dry-run', is_flag=True,
              help='Only report what would be done, send and change nothing.')
@click.option('--force', is_flag=True,
              help='Create shipments also for orders that already have one '
                   '(may create duplicates in Eurocargo).')
def ship_invoice(invoice_id, dry_run, force):
    '''Create Eurocargo shipments for all orders of INVOICE_ID.

    The orders' shipping method and status are left unchanged and no
    "shipped" signal is sent, so other handlers (e.g. warehouse) don't run.
    '''
    from app import db
    from app.invoices.models.invoice import Invoice
    from .signal_handlers import _missing_fields, create_shipments

    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        raise click.ClickException(f'Invoice {invoice_id} not found')
    orders = list(invoice.orders)
    if not orders:
        click.echo(f'Invoice {invoice_id} has no orders')
        return

    created, skipped, failed = [], [], []
    for order in orders:
        if order.params.get(URL_PARAM) and not force:
            skipped.append(order.id)
            click.echo(f'{order.id}: SKIPPED, shipment exists: {order.params[URL_PARAM]}')
            continue
        missing = _missing_fields(order)
        if missing:
            failed.append(order.id)
            click.echo(f'{order.id}: FAILED, missing {", ".join(missing)}')
            continue
        if dry_run:
            created.append(order.id)
            click.echo(f'{order.id}: would create shipment')
            continue
        error = 'see log for details'
        try:
            order.params.pop(URL_PARAM, None)
            create_shipments(order)
            url = order.params.get(URL_PARAM)
            db.session.commit()
        except Exception as exc:  # keep processing remaining orders
            db.session.rollback()
            logger.exception('Eurocargo shipment for order %s failed', order.id)
            url, error = None, str(exc)
        if url:
            created.append(order.id)
            click.echo(f'{order.id}: CREATED {url}')
        else:
            failed.append(order.id)
            click.echo(f'{order.id}: FAILED, {error}')

    prefix = 'DRY RUN: ' if dry_run else ''
    click.echo(f'{prefix}created: {len(created)}, skipped: {len(skipped)}, '
               f'failed: {len(failed)}')
    if failed:
        raise click.exceptions.Exit(1)
