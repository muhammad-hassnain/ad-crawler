from flask import Flask, request, render_template_string, redirect, url_for
import subprocess

app = Flask(__name__)

@app.route('/', methods=['GET'])
def form():
    # HTML form for input
    return render_template_string('''
        <h2>Start Ad-Crawler Session</h2>
        <form action="/start-crawler" method="post">
            <label for="profile_name">Profile Name:</label><br>
            <input type="text" id="profile_name" name="profile_name" required><br>
            <label for="port">Port:</label><br>
            <input type="text" id="port" name="port" required><br><br>
            <input type="submit" value="Start Crawler">
        </form>
    ''')

@app.route('/start-crawler', methods=['POST'])
def start_crawler():
    profile_name = request.form['profile_name']
    port = request.form['port']
    cmd = [
        "python3.11", "ad-crawler.py",
        "-p", profile_name,
        "-px", port,
        "-c", "/crawler/chrome-profile",
        "-mp", "/crawler"
    ]
    subprocess.Popen(cmd)  # Starts the crawler in a non-blocking way
    return redirect(url_for('form'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
