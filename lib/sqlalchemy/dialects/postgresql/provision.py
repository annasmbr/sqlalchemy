import time

from ... import exc
from ... import text
from ...testing.provision import create_db
from ...testing.provision import drop_db
from ...testing.provision import log
from ...testing.provision import set_default_schema_on_connection
from ...testing.provision import temp_table_keyword_args


@create_db.for_db("postgresql")
def _pg_create_db(cfg, eng, ident):
    template_db = cfg.options.postgresql_templatedb

    with eng.execution_options(isolation_level="AUTOCOMMIT").begin() as conn:
        try:
            _pg_drop_db(cfg, conn, ident)
        except Exception:
            pass
        if not template_db:
            template_db = conn.exec_driver_sql(
                "select current_database()"
            ).scalar()

        attempt = 0
        while True:
            try:
                conn.exec_driver_sql(
                    "CREATE DATABASE %s TEMPLATE %s" % (ident, template_db)
                )
            except exc.OperationalError as err:
                attempt += 1
                if attempt >= 3:
                    raise
                if "accessed by other users" in str(err):
                    log.info(
                        "Waiting to create %s, URI %r, "
                        "template DB %s is in use sleeping for .5",
                        ident,
                        eng.url,
                        template_db,
                    )
                    time.sleep(0.5)
            except:
                raise
            else:
                break


@drop_db.for_db("postgresql")
def _pg_drop_db(cfg, eng, ident):
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        with conn.begin():
            conn.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity "
                    "where usename=current_user and pid != pg_backend_pid() "
                    "and datname=:dname"
                ),
                dname=ident,
            )
            conn.exec_driver_sql("DROP DATABASE %s" % ident)


@temp_table_keyword_args.for_db("postgresql")
def _postgresql_temp_table_keyword_args(cfg, eng):
    return {"prefixes": ["TEMPORARY"]}


@set_default_schema_on_connection.for_db("postgresql")
def _postgresql_set_default_schema_on_connection(
    cfg, dbapi_connection, schema_name
):
    existing_autocommit = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    cursor.execute("SET SESSION search_path='%s'" % schema_name)
    cursor.close()
    dbapi_connection.autocommit = existing_autocommit
