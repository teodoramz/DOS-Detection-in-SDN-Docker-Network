import os
from flask import Flask, render_template, abort
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("WEBSERVER_HOST", "0.0.0.0")
DEBUG = os.getenv("WEBSERVER_DEBUG", "False").lower() in ("true", "1", "t")
PORT = int(os.getenv("WEBSERVER_PORT", 5000))

app = Flask(__name__)

posts = [
    {
        'id': 1,
        'title': 'Exploring the New Tech Trends in 2025',
        'content': (
            "The technology landscape is ever-evolving and 2025 is shaping up to be one of "
            "the most innovative years yet. From advancements in AI to groundbreaking "
            "developments in renewable energy, the future is here."
        ),
        'author': 'Emily Johnson',
        'date': 'March 15, 2025'
    },
    {
        'id': 2,
        'title': 'Sustainable Living: Tips and Tricks',
        'content': (
            "Sustainable living is not just a trend but a lifestyle shift that can help "
            "preserve the environment. Discover practical tips on reducing waste, "
            "saving energy, and making eco-friendly choices."
        ),
        'author': 'Michael Smith',
        'date': 'April 2, 2025'
    },
    {
        'id': 3,
        'title': 'Mastering Remote Work: Strategies for Success',
        'content': (
            "Remote work has redefined the traditional office environment. Learn how to "
            "stay productive, maintain a work-life balance, and create an inspiring home office setup."
        ),
        'author': 'Sophia Brown',
        'date': 'April 20, 2025'
    },
]

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/blog')
def blog():
    return render_template('blog.html', posts=posts)

@app.route('/post/<int:post_id>')
def post(post_id):
    selected_post = next((post for post in posts if post['id'] == post_id), None)
    if selected_post is None:
        abort(404)
    return render_template('post.html', post=selected_post)

if __name__ == '__main__':
    app.run(debug=DEBUG, host=HOST, port=PORT)
