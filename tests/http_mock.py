#!/usr/bin/env python3

from flask import Flask, redirect
import time


def http_mock_server():
    app = Flask(__name__)

    def create_title(title):
        return f"""
        <html>
          <head>
            <title>{title}</title>
          </head>
          <body>
          </body>
        </html>
        """

    @app.route("/simple-webpage")
    def simple_webpage():
        return create_title("Simple Webpage")

    @app.route("/another-webpage")
    def another_webpage():
        return create_title("Another Webpage")

    @app.route("/malicious-webpage")
    def malicious_webpage():
        return create_title("Malicious &#0; Webpage")

    @app.route("/long-webpage")
    def long_webpage():
        return create_title("Long Webpage" * 100)

    @app.route("/slow-webpage")
    def slow_webpage():
        time.sleep(5)
        return create_title("Slow webpage")

    @app.route("/redirecting-webpage")
    def redirecting_webpage():
        return redirect("/redirecting-webpage")

    @app.route("/redirecting-webpage-mutual")
    def redirecting_webpage_mutual():
        return redirect("/redirecting-webpage-mutual2")

    @app.route("/redirecting-webpage-mutual2")
    def redirecting_webpage_mutual2():
        return redirect("/redirecting-webpage-mutual")

    app.run(host="127.0.0.1", port=8080, threaded=True)


if __name__ == '__main__':
    http_mock_server()
