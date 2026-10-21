# -*- coding: utf-8 -*-
# Modified from https://github.com/YeomYuJun/tibero-mcp-server (commit 696e65a, MIT).
# Changes: server-side second policy check via .agents/hooks/db_sql_policy.py,
# per-env profile (TIBERO_MCP_PROFILE), approval bundle consumption, dml_audit.log,
# always rollback/close, get_table_info returns columns only.
import asyncio, json, logging, os, sys, time
from pathlib import Path
import jaydebeapi
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl
_HOOKS_DIR = Path(__file__).resolve().parents[5] / 'hooks'
sys.path.insert(0, str(_HOOKS_DIR)) if str(_HOOKS_DIR) not in sys.path else None
from db_sql_policy import (
    BUNDLE_TTL_SEC,
    DEFAULT_SESSION_TTL_SEC,
    STATE_FILE,
    approval_keyword_for_env,
    classify_sql,
    consume_write,
    has_where_clause,
    is_session_env,
    load_session,
    prod_mutation_denied,
    requires_where,
    session_allows_write,
    sql_preview,
)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tibero_mcp_server')
AUDIT_FILE = STATE_FILE.parent / 'dml_audit.log'

def get_db_config():
    config = {
        'host': os.getenv('TIBERO_HOST', 'localhost'),
        'port': os.getenv('TIBERO_PORT', '8629'),
        'sid': os.getenv('TIBERO_SID', 'tibero'),
        'user': os.getenv('TIBERO_USER'),
        'password': os.getenv('TIBERO_PASSWORD'),
    }
    if not all([config['user'], config['password']]):
        raise ValueError('Missing required database configuration')
    return config

def get_profile():
    return (os.getenv('TIBERO_MCP_PROFILE') or '').strip().lower() or 'unknown'

def get_connection():
    config = get_db_config()
    connection_string = 'jdbc:' + 'tibero' + ':thin:@{host}:{port}:{sid}'.format(**config)
    driver_path = os.getenv('CLASSPATH', 'drivers/tibero6-jdbc.jar')
    conn = jaydebeapi.connect('com.tmax.tibero.jdbc.TbDriver', connection_string, [config['user'], config['password']], driver_path)
    conn.jconn.setAutoCommit(False)
    return conn

def _audit(profile, kind, query, rowcount=None, result='ok', detail=''):
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = {'ts': time.time(), 'profile': profile, 'kind': kind, 'result': result, 'rowcount': rowcount, 'detail': detail, 'sql': sql_preview(query, 300)}
        with AUDIT_FILE.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + chr(10))
    except Exception as exc:
        logger.warning('audit log failed: %s', exc)

def _default_ttl_for_profile(profile):
    if is_session_env(profile):
        return DEFAULT_SESSION_TTL_SEC
    return BUNDLE_TTL_SEC

def enforce_execute_policy(query):
    profile = get_profile()
    kind = classify_sql(query)
    if kind == 'empty':
        return 'Empty SQL denied (server policy).'
    if kind == 'multi':
        return 'Multi-statement SQL denied (server policy).'
    if kind == 'hard_deny':
        return 'DROP/TRUNCATE denied (server policy).'
    if kind == 'unknown':
        return 'Unknown SQL kind denied (server policy).'
    if kind == 'read':
        return None
    if prod_mutation_denied(profile, query):
        return "Prod mutation denied on profile '%s': INSERT/MERGE/CREATE blocked (server policy)." % profile
    if requires_where(query) and not has_where_clause(query):
        return 'UPDATE/DELETE requires WHERE (server policy).'
    session = load_session(
        STATE_FILE,
        expected_env=profile,
        default_ttl=_default_ttl_for_profile(profile),
    )
    if not session or not session_allows_write(session):
        keyword = approval_keyword_for_env(profile)
        return "Write requires active approval '%s' for profile '%s' (server policy second check)." % (keyword, profile)
    return None

app = Server('tibero_mcp_server')


@app.list_resources()
async def list_resources():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute('SELECT table_name FROM user_tables ORDER BY table_name'); tables = cursor.fetchall()
        cursor.execute('SELECT view_name FROM user_views ORDER BY view_name'); views = cursor.fetchall()
        resources = []
        for table in tables:
            resources.append(Resource(uri='tibero://%s/data' % table[0], name='Table: %s' % table[0], mimeType='text/plain', description='Data in table: %s' % table[0]))
        for view in views:
            resources.append(Resource(uri='tibero://%s/view' % view[0], name='View: %s' % view[0], mimeType='text/plain', description='Data in view: %s' % view[0]))
        cursor.close(); conn.close(); return resources
    except Exception as e:
        logger.error('Failed to list resources: %s', e); return []

@app.read_resource()
async def read_resource(uri):
    uri_str = str(uri)
    if not uri_str.startswith('tibero://'):
        raise ValueError('Invalid URI scheme: %s' % uri_str)
    table_name = uri_str[9:].split('/')[0]
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT column_name, data_type FROM user_tab_columns WHERE table_name = '%s' ORDER BY column_id" % table_name.upper())
        columns_info = cursor.fetchall()
        cursor.execute('SELECT * FROM %s WHERE ROWNUM <= 100' % table_name)
        columns = [desc[0] for desc in cursor.description]; rows = cursor.fetchall()
        structure = 'TABLE STRUCTURE:' + chr(10) + ('-' * 50) + chr(10)
        for col_info in columns_info:
            structure += '%s | %s%s' % (col_info[0], col_info[1], chr(10))
        data = 'SAMPLE DATA:' + chr(10) + ','.join(columns) + chr(10)
        for row in rows:
            data += ','.join(map(str, row)) + chr(10)
        return structure + data
    finally:
        cursor.close(); conn.close()

@app.list_tools()
async def list_tools():
    return [
        Tool(name='execute_sql', description='Execute an SQL query on the Tibero server', inputSchema={'type':'object','properties':{'query':{'type':'string'}},'required':['query']}),
        Tool(name='get_table_info', description='Get detailed information about a table', inputSchema={'type':'object','properties':{'table_name':{'type':'string'}},'required':['table_name']}),
    ]

@app.call_tool()
async def call_tool(name, arguments):
    profile = get_profile()
    try:
        if name == 'execute_sql':
            query = arguments.get('query')
            if not query:
                raise ValueError('Query is required')
            policy_err = enforce_execute_policy(query)
            kind = classify_sql(query)
            if policy_err:
                _audit(profile, kind, query, result='deny', detail=policy_err)
                return [TextContent(type='text', text='Error: %s' % policy_err)]
            conn = get_connection(); cursor = conn.cursor()
            try:
                cursor.execute(query)
                if kind == 'read':
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()
                    if not columns:
                        _audit(profile, kind, query, rowcount=0, result='ok')
                        return [TextContent(type='text', text='Query executed successfully, but returned no columns.')]
                    result = [','.join(map(str, columns))]
                    result.extend([','.join(map(lambda x: str(x) if x is not None else 'NULL', row)) for row in rows])
                    _audit(profile, kind, query, rowcount=len(rows), result='ok')
                    return [TextContent(type='text', text='Results (%s rows):%s%s' % (len(rows), chr(10), chr(10).join(result)))]
                rowcount = cursor.rowcount
                conn.commit()
                if kind == 'write':
                    consume_write(STATE_FILE, expected_env=profile)
                _audit(profile, kind, query, rowcount=rowcount, result='ok')
                return [TextContent(type='text', text='Query executed successfully. Rows affected: %s' % rowcount)]
            finally:
                try: cursor.close()
                except Exception: pass
                try: conn.rollback()
                except Exception: pass
                try: conn.close()
                except Exception: pass
        elif name == 'get_table_info':
            table_name = arguments.get('table_name')
            if not table_name:
                raise ValueError('Table name is required')
            conn = get_connection(); cursor = conn.cursor()
            try:
                cursor.execute("SELECT column_name, data_type, data_length, nullable FROM user_tab_columns WHERE table_name = '%s' ORDER BY column_id" % table_name.upper())
                columns = cursor.fetchall()
                result = ['Table: %s' % table_name.upper(), '', 'COLUMNS:', '-' * 80, 'NAME | TYPE | LENGTH | NULLABLE', '-' * 80]
                for col in columns:
                    nullable = 'NULL' if col[3] == 'Y' else 'NOT NULL'
                    result.append('%s | %s | %s | %s' % (col[0], col[1], col[2], nullable))
                return [TextContent(type='text', text=chr(10).join(result))]
            finally:
                try: cursor.close()
                except Exception: pass
                try: conn.close()
                except Exception: pass
        else:
            raise ValueError('Unknown tool: %s' % name)
    except Exception as e:
        logger.error("Error executing tool '%s': %s", name, e)
        return [TextContent(type='text', text='Error: %s' % e)]

async def _run_stdio():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


async def _run_streamable_http(host, port):
    """localhost Streamable HTTP for the shared daemon (mcp-servers/daemon)."""
    import contextlib
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route
    from mcp.server.fastmcp.server import StreamableHTTPASGIApp
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    session_manager = StreamableHTTPSessionManager(app=app)
    asgi = StreamableHTTPASGIApp(session_manager)

    @contextlib.asynccontextmanager
    async def lifespan(_starlette_app):
        async with session_manager.run():
            yield

    starlette_app = Starlette(routes=[Route('/mcp', endpoint=asgi)], lifespan=lifespan)
    config = uvicorn.Config(starlette_app, host=host, port=int(port), log_level='info')
    await uvicorn.Server(config).serve()


async def main():
    logger.info('Starting Tibero MCP server...')
    config = get_db_config()
    logger.info('Database config: %s:%s/%s as %s (profile=%s)', config['host'], config['port'], config['sid'], config['user'], get_profile())
    # Daemon sets HARNESS_MCP_*; unset = stdio (one process per client session)
    transport = (os.environ.get('HARNESS_MCP_TRANSPORT') or 'stdio').strip().lower()
    if transport in ('streamable-http', 'http'):
        host = os.environ.get('HARNESS_MCP_HOST') or '127.0.0.1'
        port = int(os.environ.get('HARNESS_MCP_PORT') or '18761')
        logger.info('Transport=streamable-http %s:%s/mcp', host, port)
        await _run_streamable_http(host, port)
    else:
        await _run_stdio()

if __name__ == '__main__':
    asyncio.run(main())
