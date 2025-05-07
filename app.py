from flask import Flask, request, jsonify, render_template
import os
from werkzeug.utils import secure_filename
import openai
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading
import logging
from ryb import *

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def send_email(to_email, subject, body):
    from_email = os.getenv('EMAIL')
    from_password = os.getenv('EMAIL_PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        print(f"Email successfully sent")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def process_and_send_email(file_path, recipient_email):
    # Process the image with GPT-4
    books = process_image_with_gpt(file_path)
    if not books:
        return jsonify({'error': 'Unable to process image or no books found'}), 500

    book_infos = []
    for book in books:
        title = book.get('title')
        author = book.get('author')
        if title:
            book_info = get_goodreads_info(title, author)
            book_infos.append({
                'Title': title,
                'Author': book_info['author'] if book_info['author'] is not None else author_info,
                'Rating': book_info['rating_value'],
                'Rating Count': book_info['rating_count']
            })

    email_body = "<h2>Book Information</h2><ul>"
    for info in book_infos:
        email_body += f"<li><b>Title:</b> {info['Title']}<br><b>Author:</b> {info['Author']}<br><b>Rating:</b> {info['Rating']}<br><b>Rating Count:</b> {info['Rating Count']}</li><br>"
    email_body += "</ul>"
    return send_email(recipient_email, "Book Information", email_body)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files or 'email' not in request.form:
        return jsonify({'error': 'No file part or email in the request'}), 400

    file = request.files['file']
    recipient_email = request.form['email']
    if file.filename == '' or recipient_email == '':
        return jsonify({'error': 'No selected file or email'}), 400

    if file and allowed_file(file.filename):
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        threading.Thread(target=process_and_send_email, args=(file_path, recipient_email)).start()
        return jsonify({'message': 'Processing started, you will receive an email soon!'}), 200
    else:
        return jsonify({'error': 'File type not allowed'}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
