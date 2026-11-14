"""Pool de conexiones a PostgreSQL (psycopg 3, síncrono).

Los endpoints son funciones `def` normales: FastAPI las ejecuta en un pool de
hilos, así que el acceso síncrono no bloquea el bucle de eventos. Se evita el
modo asíncrono de psycopg porque en Windows requiere cambiar el event loop.
"""
from collections.abc import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def _configure(conn: Connection) -> None:
    conn.execute("SET search_path = cardia, public")
    conn.commit()


def open_pool(url: str) -> ConnectionPool:
    global _pool
    _pool = ConnectionPool(
        url, min_size=1, max_size=10, open=True,
        kwargs={"row_factory": dict_row}, configure=_configure,
    )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[Connection]:
    """Dependencia de FastAPI: una conexión por petición, con commit al terminar."""
    if _pool is None:
        raise RuntimeError("El pool de base de datos no está abierto")
    with _pool.connection() as conn:
        yield conn
