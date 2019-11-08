from flask import Flask
import socket

app = Flask(__name__)
host = socket.gethostname()


@app.route('/')
def hello():
    return 'Hello ! My hostname is %s\n' % host


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
