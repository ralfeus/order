from celery.utils.log import get_task_logger
from app import celery, db
from app.settings.models.setting import Setting

@celery.task
def copy_subtree(root_id=None):
    logger = get_task_logger('copy_subtree')
    if root_id is None:
        root_id = Setting.query.get('network.root_id')
    if root_id is None:
        return
    result = db.session.execute('SELECT 1 FROM order_master_common.network_nodes WHERE id = :id',
        {'id': root_id})
    if not result or not result.rowcount:
        logger.warning(result)
        return
    db.session.execute('TRUNCATE network_nodes')
    result = db.session.execute('''
        INSERT INTO network_nodes
        WITH RECURSIVE cte AS (
            SELECT when_created,when_changed,id,name,`rank`,highest_rank,
                center,country,signup_date,pv,network_pv,
                CAST(NULL AS CHAR(10)) AS parent_id,
                left_id,right_id,built_tree
            FROM order_master_common.network_nodes WHERE id = :root_id
            UNION
            SELECT n.* 
            FROM
                order_master_common.network_nodes AS n 
                JOIN cte ON n.parent_id = cte.id
        ) SELECT * FROM cte
        ''', {'root_id': root_id})
    if result.rowcount:
        db.session.commit()
        logger.info("Copied %s rows", result.rowcount)
    else:
        logger.warning(result)
