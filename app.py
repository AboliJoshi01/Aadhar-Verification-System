from flask import Flask, render_template, request
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import re
import os
import mysql.connector

# Initialize Flask app
app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MySQL Database Connection
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'WJ28@krhps',
    'database': 'aadhaar_db'
}

# Routes for Home, About, and Contact pages
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Function to check if Aadhaar number exists in DB
def check_aadhar_in_db(aadhar_number):
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "SELECT * FROM aadhar_info WHERE aadhar_number = %s"
        cursor.execute(query, (aadhar_number,))
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        print("Database error:", e)
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Function to extract Aadhaar number and name
def extract_name_and_aadhar(text):
    aadhar_match = re.search(r'\b\d{4}\s\d{4}\s\d{4}\b', text)
    aadhar_number = aadhar_match.group() if aadhar_match else None
    name = None
    if aadhar_match:
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        for i, line in enumerate(lines):
            if aadhar_number in line:
                for j in range(i-1, max(i-7, -1), -1):
                    possible_name = lines[j].strip()
                    if possible_name and re.match(r'^[A-Za-z ]+$', possible_name) and len(possible_name.split()) >= 2:
                        name = possible_name
                        break
                break
    if not name:
        name = "Name Not Found"
    return name, aadhar_number

# Function to insert Aadhaar data into DB
def insert_aadhar_into_db(aadhar_number, name):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "INSERT INTO aadhar_info (aadhar_number, name) VALUES (%s, %s)"
        cursor.execute(query, (aadhar_number, name))
        connection.commit()
    except Exception as e:
        print("Database Insertion Error:", e)
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Route for uploading and verifying Aadhaar PDF
@app.route('/', methods=['GET', 'POST'])
def upload_aadhar():
    verification_status = None
    extracted_aadhar = None
    error = None

    if request.method == 'POST':
        if 'aadhar_pdf' not in request.files:
            error = "No file part"
            return render_template('index.html', error=error)

        file = request.files['aadhar_pdf']
        password = request.form.get('pdf_password')

        if file.filename == '':
            error = "No selected file"
            return render_template('index.html', error=error)

        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            try:
                doc = fitz.open(filepath)

                if doc.is_encrypted:
                    if not password:
                        error = "PDF is encrypted. Please provide the password."
                        return render_template('index.html', error=error)
                    if not doc.authenticate(password):
                        error = "Incorrect password provided!"
                        return render_template('index.html', error=error)

                text = ""
                for page in doc:
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_text = pytesseract.image_to_string(img)
                    page_text = page_text.encode('utf-8', errors='ignore').decode('utf-8')  # <-- ADD this line here
                    text += page_text + "\n"

                extracted_aadhar = extract_name_and_aadhar(text)[1]

                if extracted_aadhar:
                    if check_aadhar_in_db(extracted_aadhar):
                        verification_status = "Verified Successfully ✅"
                    else:
                        verification_status = "Verification Failed ❌"
                else:
                    error = "No Aadhaar number found in the PDF."

            except Exception as e:
                error = f"Error processing PDF: {str(e)}"

    return render_template('index.html', verification_status=verification_status,
                       extracted_aadhar=extracted_aadhar, error=error)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
