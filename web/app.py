"""MCPBook web backend."""

from flask import Flask, render_template, jsonify

from web.version import get_connect_message, get_version

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", connect_message=get_connect_message())


@app.route("/api/status")
def status():
    return jsonify({"connect": get_connect_message(), "version": get_version()})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
