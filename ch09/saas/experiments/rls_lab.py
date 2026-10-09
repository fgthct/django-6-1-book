"""Row Level Security on a test table: what it protects, and what it doesn't."""
import os

import psycopg

PORT = os.environ.get("DB_PORT", "5432")
APP = f"host=localhost port={PORT} dbname=saas user=saas password=saas"
# A connection as the database superuser (the lab shows that it bypasses RLS). On Debian/Ubuntu,
# run the script as the postgres system user, or set SUPER_DSN to a DSN of your own.
SUPER = os.environ.get("SUPER_DSN", f"host=/var/run/postgresql port={PORT} dbname=saas user=postgres")


def count(conn, org=None):
    with conn.transaction():
        if org is not None:
            conn.execute("SELECT set_config('app.org', %s, true)", (org,))
        return conn.execute("SELECT count(*) FROM rls_test").fetchone()[0]


app = psycopg.connect(APP, autocommit=True)
app.execute("DROP TABLE IF EXISTS rls_test")
app.execute("CREATE TABLE rls_test (id serial PRIMARY KEY, org text NOT NULL, note text)")
app.execute("INSERT INTO rls_test (org, note) SELECT 'acme', 'a' || g FROM generate_series(1, 5) g")
app.execute("INSERT INTO rls_test (org, note) SELECT 'rossi', 'r' || g FROM generate_series(1, 3) g")
total = app.execute("SELECT count(*) FROM rls_test").fetchone()[0]

print(f"{'without RLS, tenant ' + repr('acme') + ':':50}{count(app, 'acme')} rows ({total} in all)")

app.execute("ALTER TABLE rls_test ENABLE ROW LEVEL SECURITY")
app.execute("""CREATE POLICY by_tenant ON rls_test
    USING (org = current_setting('app.org', true))
    WITH CHECK (org = current_setting('app.org', true))""")
print(f"{'RLS on, but the owner is exempt:':50}{count(app, 'acme')} rows  <- the trap")

app.execute("ALTER TABLE rls_test FORCE ROW LEVEL SECURITY")
print(f"{'RLS forced, tenant ' + repr('acme') + ':':50}{count(app, 'acme')} rows")
print(f"{'RLS forced, tenant ' + repr('rossi') + ':':50}{count(app, 'rossi')} rows")
print(f"{'RLS forced, no tenant:':50}{count(app)} rows")
try:
    with app.transaction():
        app.execute("SELECT set_config('app.org', 'acme', true)")
        app.execute("INSERT INTO rls_test (org, note) VALUES ('rossi', 'smuggled')")
except psycopg.errors.InsufficientPrivilege as e:
    print(f"{'write to the wrong tenant:':50}{str(e).strip()}")

su = psycopg.connect(SUPER, autocommit=True)
n = su.execute("SELECT count(*) FROM rls_test").fetchone()[0]
print(f"{'a superuser, even with RLS forced:':50}{n} rows  <- ignores everything")
app.execute("DROP TABLE rls_test")
