import subprocess
import sys

from flask import Flask, render_template, request, Response

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    mode = request.form.get("mode", "question")
    query = request.form.get("query", "").strip()
    if not query:
        return Response("empty query", status=400)

    cmd = [sys.executable, "rag_qa.py"]
    if mode == "search":
        cmd.append("--search")
    cmd.append(query)

    def generate():
        import os
        import re

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        ansi_re = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
        for line in proc.stdout:
            clean = ansi_re.sub("", line).replace("\r", "").replace("\x1b[K", "")
            if clean.strip():
                yield clean
        proc.wait()

    return Response(generate(), content_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
