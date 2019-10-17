import datetime
import logging
import os
import socket
import requests
import tempfile


from flask import Flask, request, jsonify, make_response
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy

import datetime
from google.cloud import storage
storage_client = storage.Client()
import random
from google.cloud import bigquery
import string
client = bigquery.Client()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

cors = CORS(app, send_wildcard=True)
app.config['CORS_HEADERS'] = 'Content-Type'
from google.cloud import pubsub_v1

project_id = "cloud2-task2"
topic_name = "projects/cloud2-task2/topics/todo"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_name)

db = SQLAlchemy(app)

def convert_todo_to_string(x):
    return {
        "id": x.id,
        "user": x.user,
        "text": x.text,
        "start": (x.start - datetime.datetime(1970, 1, 1)).total_seconds() * 1000 if x.start != None else None,
        "end": (x.end - datetime.datetime(1970, 1, 1)).total_seconds() * 1000 if x.end != None else None,
    }

def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def create_file(user_blob_name, content_file):
    """Returns the blob name
    
    Arguments:
        content {string} -- The content of the file.
    """
    bucket_name = 'todo-bucket-data-wipe'
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(user_blob_name)
    blob.upload_from_filename(content_file)
    return blob.generate_signed_url(datetime.timedelta(1))



class User(db.Model):
    username = db.Column(db.String, primary_key=True)
    password = db.Column(db.String)
    delete = db.Column(db.Boolean)
    url = db.Column(db.String)
    blob_name = db.Column(db.String)

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.delete = False
        self.url = None
        self.blob_name = ''

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String, db.ForeignKey('user.username', ondelete='CASCADE'), nullable=False)
    text = db.Column(db.String, nullable=False)
    start = db.Column(db.DateTime)
    end = db.Column(db.DateTime)

    def __init__(self, todo_text, user):
        self.text = todo_text
        self.user = user


db.create_all()
db.session.commit()

# CORS manual decorator

# @app.after_request
# def after_request(response):
#     response.headers.add('Access-Control-Allow-Origin', '*')
#     response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
#     response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
#     return response

@app.route('/backend/login', methods=["POST"])
@cross_origin()
def login_user():
    username = request.json['userName']
    password = request.json['password']
    try:
        user_name_record = User.query.filter_by(username=username).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return jsonify({
            "match": False
        })
    if user_name_record.password == password:
        return jsonify(
            {
                "match": True,
                "removeUser": user_name_record.delete,
                "dataUrl": user_name_record.url
            }
        )
    else:
        return jsonify({
            "match": False
        })



@app.route('/backend/register', methods=["POST"])
@cross_origin()
def add_user():
    username = request.json['userName']
    password = request.json['password']

    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return make_response({}, 200)


@app.route('/backend/todos', methods=["POST"])
@cross_origin()
def todos():
    username = request.json['userName']
    try:
        todo_mode = request.json['todo_mode']
    except KeyError:
        todo_mode = None
    matching_todos = {}
    if (todo_mode == 'done'):
        matching_todos = Todo.query.filter(sqlalchemy.and_(Todo.user == username, Todo.start != None, Todo.end != None)).all()
    elif (todo_mode == 'not-done'):
        matching_todos = Todo.query.filter(sqlalchemy.and_(Todo.user == username, Todo.start == None, Todo.end == None)).all()
    else:
        matching_todos = Todo.query.filter(Todo.user == username).all()
    
    todos_list = list(map(convert_todo_to_string, matching_todos))
    return jsonify(todos_list)


@app.route('/backend/create-todo', methods=["POST"])
@cross_origin()
def create_todo():
    text = request.json['text']
    username = request.json['userName']

    try:
        new_todo = Todo(text, username)
        db.session.add(new_todo)
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        return make_response({}, 400)
    return make_response({}, 200)

@app.route('/backend/start-todo', methods=['POST'])
@cross_origin()
def start_todo():
    username = request.json['userName']
    todo_id = request.json['id']

    todo_record = Todo.query.filter_by(id=todo_id).first()

    todo_record.start = datetime.datetime.now()

    db.session.commit()

    return make_response({}, 200)

@app.route('/backend/end-todo', methods=['POST'])
@cross_origin()
def end_todo():
    username = request.json['userName']
    todo_id = request.json['id']

    todo_record = Todo.query.filter_by(id=todo_id).first()

    todo_record.end = datetime.datetime.now()

    db.session.commit()

    return make_response({}, 200)

@app.route('/backend/data-ready', methods=['POST'])
@cross_origin()
def data_ready():
    username = request.json['userName']

    user = User.query.filter_by(username=username).first()
    if user.url:
        return make_response({
            "url": user.url
        }, 200)
    subscription_name = 'todo-subscription'

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(
        project_id, subscription_name)
    
    messages = subscriber.pull(subscription_path, 10, True)
    for message in messages.received_messages:
        if 'username' not in message.message.attributes or 'delete_user' in message.message.attributes:
            continue
        if message.message.attributes['username'] == username:
            user = User.query.filter_by(username=username)
            user.data_url = message.message.attributes['url']
            db.session.commit()
            subscriber.acknowledge(subscription_path, [message.ack_id])
            
            return make_response({
                'url': message.message.attributes['url']
            }, 200)
    return make_response({}, 200)


@app.route('/backend/data-out', methods=['POST'])
@cross_origin()
def delete_data():
    username = request.json['userName']

    subscriber = pubsub_v1.SubscriberClient()
    data = list(map(convert_todo_to_string, Todo.query.filter_by(user=username).all()))
    user = User.query.filter_by(username=username).first()
    user.delete = True
    file_name = randomString()
    f = open(file_name, 'w+')
    f.write(str(data))
    f.close()
    data_uri = create_file(file_name, file_name)
    user.url = data_uri
    user.blob_name = file_name
    db.session.commit()
    publisher.publish(topic_name, b'', username=username, url=data_uri)
    os.remove(file_name)
    return make_response({}, 200)

@app.route('/backend/delete-user', methods=['POST'])
@cross_origin()
def delete_user():
    username = request.json['userName']
    user = User.query.filter_by(username=username).first()

    publisher.publish(topic_name, b'', username=username, delete_user='true', delete_user_file=user.blob_name)
    return make_response({}, 200)

@app.route('/backend/users', methods=['POST'])
@cross_origin()
def number_of_users():
    query_job = client.query("""
            SELECT * FROM EXTERNAL_QUERY(\"cloud2-task2.asia-southeast1.todo-database\", \"SELECT COUNT(*) from todo;\");
            """)
    results = list(query_job.result())
    return make_response({
        "count": results[0].get('count')
        }, 200)