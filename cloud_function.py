import base64
from os import getenv

from psycopg2 import OperationalError
from psycopg2.pool import SimpleConnectionPool
# Imports the Google Cloud client library
from google.cloud import storage
# Instantiates a client
storage_client = storage.Client()

# The name for the new bucket
bucket_name = 'todo-bucket-data-wipe'

CONNECTION_NAME = getenv(
  'INSTANCE_CONNECTION_NAME',
  'cloud2-task2:asia-southeast1:todo-database')
DB_USER = getenv('POSTGRES_USER', 'rhitik')
DB_PASSWORD = getenv('POSTGRES_PASSWORD', 'test123')
DB_NAME = getenv('POSTGRES_DATABASE', 'test')

pg_config = {
  'user': DB_USER,
  'password': DB_PASSWORD,
  'dbname': DB_NAME
}

def hello_pubsub(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    print(pubsub_message)


# Connection pools reuse connections between invocations,
# and handle dropped or expired connections automatically.
pg_pool = None


def __connect(host):
    """
    Helper function to connect to Postgres
    """
    global pg_pool
    pg_config['host'] = host
    pg_pool = SimpleConnectionPool(1, 1, **pg_config)


def postgres_demo(event, context):
    global pg_pool
    print(event)

    if (event['attributes']['delete_user'] != 'true'):
        return False
    if event['attributes'].get('delete_user_file'):
        storage.bucket.Bucket(storage_client, bucket_name).delete_blob(event['attributes'].get('delete_user_file'))


    username = event['attributes']['username']

    # Initialize the pool lazily, in case SQL access isn't needed for this
    # GCF instance. Doing so minimizes the number of active SQL connections,
    # which helps keep your GCF instances under SQL connection limits.
    if not pg_pool:
        try:
            __connect(f'/cloudsql/{CONNECTION_NAME}')
        except OperationalError:
            # If production settings fail, use local development ones
            __connect('localhost')

    
    # Remember to close SQL resources declared while running this function.
    # Keep any declared in global scope (e.g. pg_pool) for later reuse.
    with pg_pool.getconn() as conn:
        cursor = conn.cursor()
        user_delete_query = "DELETE FROM \"user\" WHERE username='{}';".format(username)
        todo_delete_query = "DELETE FROM todo WHERE user='{}';".format(username)
        print("Deleting Users and TODOs")
        print("Running queries: \n{} \n{}".format(user_delete_query, todo_delete_query))
        cursor.execute(user_delete_query)
        cursor.execute(todo_delete_query)
        conn.commit()
        pg_pool.putconn(conn)
        return True

# if __name__ == '__main__':
#     postgres_demo({
#         '@type': 'type.googleapis.com/google.pubsub.v1.PubsubMessage',
#         'attributes': {'delete_user': 'true', 'username': 'user_ip'},
#         'data': ''
#     }, "")
    