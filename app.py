from flask import Flask
import sqlalchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URL'] = 'sqlite:///db.db'


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"