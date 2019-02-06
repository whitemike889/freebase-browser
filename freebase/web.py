import json
from flask import Flask, render_template, request, abort, redirect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from freebase.model import Topic, get_db_url

app = Flask(__name__)
engine = create_engine(get_db_url(), poolclass=NullPool)
Session = sessionmaker(bind=engine)


@app.route('/')
def main():
    return render_template('main.html')


@app.route('/freebase/<path:path>')
def base(path):
    return redirect(path)


@app.route('/<path:path>')
def get_entity(path):
    path = '/' + path
    db = Session()
    try:
        topic = None
        if path.startswith('/m/') or path.startswith('/g/'):
            topic = db.query(Topic).filter_by(mid=path).first()
        if topic is None:
            topic = db.query(Topic).filter_by(textid=path).first()
        if topic is None:
            topic = db.query(Topic).join(Topic.keys).filter_by(key=path).first()
        if topic is None:
            abort(404)

        if topic.mid is not None and path != topic.mid:
            return redirect(topic.mid, code=303)  # We prefer the MID

        mimetype = request.accept_mimetypes.best_match(['text/html', 'application/ld+json', 'application/json'])
        if mimetype == 'application/json' or mimetype == 'application/ld+json':
            return app.response_class(json.dumps(topic.jsonld), mimetype=mimetype)
        else:
            return render_template('topic_display.html', topic=to_full_dict(topic))
    finally:
        db.close()


def to_simple_dict(topic):
    return {
        'id': topic.textid if topic.textid else topic.mid,
        'url': '/freebase{}'.format(topic.mid if topic.mid else topic.textid),
        'label': content_negotiation(topic.labels),
        'description': content_negotiation(topic.descriptions)
    }


def to_full_dict(topic):
    desc = to_simple_dict(topic)
    desc['canonical'] = 'http://www.freebase.com{}'.format(topic.textid if topic.textid else topic.mid)
    desc['notable_types'] = [to_simple_dict(type.type) for type in topic.types if type.notable]
    desc['other_types'] = [to_simple_dict(type.type) for type in topic.types if not type.notable]
    desc['fkeys'] = [key.key for key in topic.keys]
    desc['jsonld'] = json.dumps(topic.jsonld)
    return desc


def get_topic(**filters):
    db = Session()
    try:
        topic = db.query(Topic).filter_by(**filters).first()
        if topic is None:
            abort(404)

        mimetype = request.accept_mimetypes.best_match(['text/html', 'application/ld+json', 'application/json'])
        if mimetype == 'application/json' or mimetype == 'application/ld+json':
            return app.response_class(json.dumps(topic.jsonld), mimetype=mimetype)
        else:
            return render_template('topic_display.html', topic=to_full_dict(topic))
    finally:
        db.close()


def content_negotiation(labels):
    languages = [label.language for label in labels]
    languages.append('en')
    best_language = request.accept_languages.best_match(languages)
    for label in labels:
        if label.language == best_language:
            return label
    return None
