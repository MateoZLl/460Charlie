import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import uuid
from datetime import timedelta

# Initialize Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static', static_url_path='/static')

# Secret key for session management
app.secret_key = 'your_secret_key'

# Configure SQLite database
instance_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')

# Ensure the instance folder exists
if not os.path.exists(instance_folder):
    os.makedirs(instance_folder)

# Set the database URI
db_path = os.path.join(instance_folder, "users.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Make session permanent to last across page reloads and browser sessions
app.permanent_session_lifetime = timedelta(days=7)  # Session lasts for 7 days

@app.before_request
def make_session_permanent():
    session.permanent = True

# Check if the database file exists and create it if necessary
if not os.path.exists(db_path):
    with app.app_context():
        db.create_all()

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    coins = db.Column(db.Integer, default=0)  # Add the coins field with a default value of 0

# Files model to store uploaded PDFs
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Primary key for the File table
    filename = db.Column(db.String(256), nullable=False)  # Filename with UUID (or the complete file name)
    original_filename = db.Column(db.String(256), nullable=False)  # Original filename (without UUID)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key to link the file to the user
    user = db.relationship('User', backref=db.backref('files', lazy=True))  # Establishes the one-to-many relationship with the User model

    def __repr__(self):
        return f'<File {self.original_filename}>'

# Notes model to store user notes for each page of the PDF
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_text = db.Column(db.Text, nullable=False)  # The note text
    page_number = db.Column(db.Integer, nullable=False)  # The page number for which the note is written
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)  # Link to the PDF file
    file = db.relationship('File', backref=db.backref('notes', lazy=True))  # Relationship to File model
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Link to the user who created the note
    user = db.relationship('User', backref=db.backref('notes', lazy=True))  # Relationship to User model

    def __repr__(self):
        return f"<Note {self.id} for {self.page_number} of file {self.file.original_filename}>"





# ---------------------- FIRSTPAGE -------------------------
@app.route('/')
def first():
    return render_template('firstpage.html')  # Serve the first page

# ---------------------- SIGNUP PAGE -------------------------
@app.route('/signup')
def signup():
    return render_template('signup.html')  # Serve the signup page

# ---------------------- LOGIN PAGE -------------------------
@app.route('/login')
def login():
    return render_template('login.html')  # Serve the login page

# ---------------------- QUIZ PAGE -------------------------
@app.route('/quiz')
def quiz():
    user_coins = session.get('user_coins')
    return render_template('quiz.html', coins=user_coins)

# ---------------------- LOGIN LOGIC -------------------------
@app.route('/submit-login', methods=['POST'])
def login_post():
    data = request.get_json()  # Get the data from the JSON request
    email = data.get('email')
    password = data.get('password')

    if email and password:
        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # If the email exists, redirect to home
            session['user_name'] = existing_user.name  # Set session data to the existing user's name
            session['user_coins'] = existing_user.coins  # Store coins in session
            session['user_id'] = existing_user.id  # Store user ID in session
            return jsonify({"message": "Login successful", "user_name": existing_user.name}), 200  # Return success response

        return jsonify({"error": "User does not exist"}), 400

    # If something goes wrong (e.g., data is missing), show an error
    return jsonify({"error": "Missing information"}), 400

# ---------------------- SIGNUP LOGIC -------------------------
@app.route('/submit-signup', methods=['POST'])
def submit_signup():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')

    if name and email and password:
        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Error: User already exists.", 400

        # Hash the password using the PBKDF2 algorithm
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Create a new user instance with coins set to 0
        new_user = User(name=name, email=email, password=hashed_password)

        # Add the user to the database
        db.session.add(new_user)
        db.session.commit()

        # Store the user's name and coins in the session
        session['user_name'] = new_user.name
        session['user_coins'] = new_user.coins  # Store coins in session
        session['user_id'] = new_user.id  # Store user ID in session

        # Redirect to the /home route after successful signup
        return redirect(url_for('home'))  # Redirect to the home route

    # If something goes wrong (e.g., data is missing), show an error
    return "Error: Missing information.", 400

# ---------------------- HOME PAGE -------------------------
@app.route('/home')
def home():
    # Retrieve the user's name and coin amount from the session
    user_name = session.get('user_name')
    user_coins = session.get('user_coins')  # Get coins from session
    return render_template('home.html', name=user_name, coins=user_coins)  # Pass coins to the template

# ---------------------- BOOKLOG PAGE -------------------------
@app.route('/bookLog')
def bookLog():
    user_coins = session.get('user_coins')
    return render_template('booklog.html', coins=user_coins)

# ---------------------- STARTREAD PAGE -------------------------
@app.route('/startReading')
def startReading():
    pdf_filename = session.get('pdf_filename')
    pdf_original_filename = session.get('pdf_original_filename')
    user_coins = session.get('user_coins')

    # Ensure we have a valid file in session
    if pdf_filename and pdf_original_filename:
        return render_template('startread.html', pdf_filename=pdf_filename, pdf_original_filename=pdf_original_filename, coins=user_coins)
    else:
        # Redirect to home if no PDF is available
        return redirect(url_for('home'))
    
# ---------------------- READER PAGE -------------------------
@app.route('/pageReader', methods=['POST', 'GET'])
def pageReader():
    if request.method == 'POST':
        # Handle the POST request to set reading time
        data = request.get_json()
        selected_time = data.get('time')
        print(selected_time)
        
        if selected_time is not None:
            session['reading_time'] = selected_time * 60
            session.modified = True  # Ensure session is updated
            print("Updated reading time in session:", session['reading_time'])
            return jsonify({"message": "Time set successfully!"}), 200
        else:
            return jsonify({"error": "Invalid time data"}), 400
    else:
        # Handle the GET request to render the page
        pdf_filename = session.get('pdf_filename')
        user_coins = session.get('user_coins')
        reading_time = session.get('reading_time', 300)  # Default to 5 min if not set
        print("Reading time:", reading_time)

        if pdf_filename and reading_time:
            return render_template(
                'reader.html',
                pdf_filename=pdf_filename,
                pdf_base_filename=os.path.basename(pdf_filename),
                coins=user_coins,
                reading_time=reading_time
            )
        else:
            # Redirect to home if no PDF or reading time is available
            return redirect(url_for('home'))

# ---------------------- SAVE NOTES LOGIC -------------------------
@app.route('/save-notes', methods=['POST'])
def save_notes():
    data = request.get_json()
    pdf_filename = data.get('pdf_filename')
    page_number = data.get('page_number')
    notes = data.get('notes')  # Array of notes for the page
    user_id = session.get('user_id')  # Assuming the user is logged in and the user_id is stored in the session

    if not pdf_filename or page_number is None or notes is None or user_id is None:
        return jsonify({"error": "Missing data"}), 400

    # Get the File record associated with the PDF
    file = File.query.filter_by(filename=pdf_filename).first()

    if not file:
        return jsonify({"error": "File not found"}), 404

    # Delete all existing notes for this user, page, and file
    Note.query.filter_by(file_id=file.id, page_number=page_number, user_id=user_id).delete()

    # Commit the delete operation
    db.session.commit()

    # Save each new note for the given page
    for note_text in notes:
        note = Note(
            note_text=note_text,
            page_number=page_number,
            file_id=file.id,
            user_id=user_id
        )
        db.session.add(note)

    # Commit the changes to the database
    db.session.commit()

    return jsonify({"message": "Notes saved successfully!"}), 200

# ---------------------- FETCHING NOTES LOGIC -------------------------
@app.route('/get-notes', methods=['GET'])
def get_notes():
    pdf_filename = request.args.get('pdf_filename')
    page_number = request.args.get('page_number')

    if not pdf_filename or page_number is None:
        return jsonify({"error": "Missing data"}), 400

    # Get the File record associated with the PDF
    file = File.query.filter_by(filename=pdf_filename).first()

    if not file:
        return jsonify({"error": "File not found"}), 404

    # Get the notes for the given page
    notes = Note.query.filter_by(file_id=file.id, page_number=page_number).all()

    # Format the notes into a list of dictionaries
    notes_data = [{"id": note.id, "note_text": note.note_text} for note in notes]

    return jsonify({"notes": notes_data}), 200

# ---------------------- COIN LOGIC -------------------------
@app.route('/update_coins', methods=['POST'])
def update_coins():
    try:
        data = request.json  # Get the JSON data from the frontend
        coins_earned = data.get('coins_earned', 0)

        # Update the coins in the session or database
        if 'user_coins' in session:
            session['user_coins'] += coins_earned
        else:
            session['user_coins'] = coins_earned

        return jsonify({
            'status': 'success',
            'new_total': session['user_coins']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ---------------------- FILE SERVING -------------------------
@app.route('/backend/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory('../backend/uploads', filename)

# ---------------------- FILE UPLOADING -------------------------
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../backend/uploads')
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------------- FILE UPLOAD LOGIC -------------------------
@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        # Generate a unique filename to avoid overwriting
        unique_filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # Extract the original file name (minus UUID and .pdf)
        og_filename = secure_filename(file.filename).replace('.pdf', '')

        # Save file metadata in the database
        new_file = File(filename=unique_filename, original_filename=og_filename, user_id=session.get('user_id'))
        db.session.add(new_file)
        db.session.commit()

        # Update session with the latest uploaded file's details
        session['pdf_filename'] = ('/backend/uploads/' + unique_filename)
        session['pdf_original_filename'] = og_filename
        print('/backend/uploads/' + unique_filename)

        return jsonify({
            "message": "File uploaded successfully",
            "filename": unique_filename,
            "ogFilename": og_filename  # Include the original file name in the response
        }), 200
    return jsonify({"message": "Invalid file type"}), 400

# ---------------------- GETTING UPLOAD LOGIC -------------------------
@app.route('/api/get-uploads', methods=['GET'])
def get_uploads():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"message": "User not logged in"}), 401

        # Get the list of files uploaded by the logged-in user
        user_files = File.query.filter_by(user_id=user_id).all()

        file_urls = []
        for file in user_files:
            file_urls.append({
                'pdf': f'/backend/uploads/{file.filename}',  # File URL with UUID
                'bookname': file.original_filename  # Original filename without UUID and .pdf
            })
        
        return jsonify(file_urls), 200
    except Exception as e:
        print(f"Error retrieving files: {str(e)}")
        return jsonify({"message": f"Error retrieving files: {str(e)}"}), 500

# ---------------------- PDF SESSION LOGIC -------------------------
@app.route('/set-pdf-session', methods=['POST'])
def set_pdf_session():
    data = request.get_json()
    filename = data.get('filename')
    original_filename = data.get('original_filename')

    if filename and original_filename:
        session['pdf_filename'] = filename
        session['pdf_original_filename'] = original_filename
        print(filename)
        return jsonify({"message": "Session data set successfully"}), 200
    else:
        return jsonify({"error": "Invalid data"}), 400

# ---------------------- LOGOUT LOGIC -------------------------
@app.route('/logout')
def logout():
    # Clear the user's session
    session.clear()
    # Redirect to the first page
    return redirect(url_for('first'))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)