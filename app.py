import os
from flask import Flask, render_template, jsonify, request, send_file, redirect, session, url_for
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import numpy as np
import joblib
import csv

# Initialize Flask app
app = Flask(__name__)

# Load your dataset
newdata = pd.read_csv('Data.csv', header=0)

# Define the path for the CSV file
csv_file = 'Feedback.csv'

# Function to ensure the CSV file has the correct header if it doesn't exist
def ensure_csv_has_header():
    if not os.path.exists(csv_file):
        with open(csv_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["SEAT", "FEEDBACK"])  # Writing column headers only if the file doesn't exist
# Function to check user credentials from Login.csv
def verify_credentials(number, password):
    with open('Login.csv', mode='r') as file:
        csvreader = csv.DictReader(file)
        for row in csvreader:
            if row['number'] == number:
                if row['password'] == password:
                    return "Success"
                else:
                    return "Wrong password"
        return "Account does not exist"

# Route for the login page
@app.route('/', methods=['GET', 'POST'])
def login():
    message = ''
    success_message = ''
    if request.method == 'POST':
        number = request.form['number']
        password = request.form['password']
        verification = verify_credentials(number, password)
        if verification == "Success":
            # Redirect to home.html after successful login
            return redirect(url_for('home'))  # Redirect to home route
        else:
            message = verification
    return render_template('login.html', message=message, success_message=success_message)

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    message = ''
    success_message = ''
    if request.method == 'POST':
        number = request.form['number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Validate number length
        if len(number) != 10:
            message = "Number must be exactly 10 digits."
        # Check if passwords match
        elif password != confirm_password:
            message = "Passwords do not match."
        else:
            # Check if the number already exists
            with open('Login.csv', mode='r') as file:
                csvreader = csv.DictReader(file)
                for row in csvreader:
                    if row['number'] == number:
                        message = "Account already exists. Please login."
                        return render_template('register.html', message=message, success_message=success_message)

            # If all validations pass, save to Login.csv
            with open('Login.csv', mode='a', newline='') as file:
                csvwriter = csv.writer(file)
                csvwriter.writerow([number, password])
            
            # Redirect to login with success message
            success_message = "Account created successfully! Please login."
            return redirect(url_for('login'))

    return render_template('register.html', message=message, success_message=success_message)

# Home route after successful login
@app.route('/home')
def home():
    return render_template('home.html')  # Rendering home.html after login success

# Analysis page
@app.route('/analysis')
def analysis():
    return render_template('index.html')  # Rendering index.html for analysis



# Prediction page
@app.route('/prediction')
def prediction():
    return render_template('prediction.html')  # Rendering prediction.html
# Feedback form route
@app.route('/feedback')
def feedback_form():
    return render_template('feedback.html')
# Feedback submission route
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    # Ensure the CSV file has the correct header before writing data
    ensure_csv_has_header()

    # Get data from form
    seat = request.form.get('seat')
    feedback = request.form.get('feedback')

    # Append the feedback to the CSV file
    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([seat, feedback])

    return redirect(url_for('home'))  # Redirect back to the form page after submission

# Endpoint to get available options for colleges, courses, categories, and genders for dynamic dropdowns
@app.route('/get_options', methods=['GET'])
def get_options():
    colleges = newdata['NAME'].unique().tolist()
    courses = newdata['COURSE'].unique().tolist()
    categories = newdata['CATEGORY'].unique().tolist()
    genders = newdata['GENDER'].unique().tolist()

    return jsonify({
        'colleges': colleges,
        'courses': courses,
        'categories': categories,
        'genders': genders
    })

# Endpoint to make predictions based on user inputs
@app.route('/make_prediction', methods=['POST'])
def make_prediction():
    data = request.json
    college = data['college'].upper().strip()
    course = data['course'].upper().strip()
    category = data['category'].lower().strip()
    gender = data['gender'].lower().strip()
    user_rank = int(data['rank'].strip())

    # Filter the dataset based on user inputs
    filtered_data = newdata[(
        newdata['NAME'].str.upper() == college) & 
        (newdata['COURSE'].str.upper() == course) & 
        (newdata['CATEGORY'].str.lower() == category) & 
        (newdata['GENDER'].str.lower() == gender)
    ]

    # Calculate average closing rank if filtered data is not empty
    if not filtered_data.empty:
        avg_close_rank = filtered_data['CLOSE RANK'].mean()

        # Compare user rank with average close rank
        if user_rank <= avg_close_rank:
            prediction = "You will most likely get a seat."
        else:
            prediction = "You will most likely not get a seat."
    else:
        prediction = "No data found for the selected options."

    return jsonify({'prediction': prediction})

# Display graph based on user inputs for analysis
@app.route('/display_graph', methods=['POST'])
def display_graph():
    data = request.form
    college = data['college'].upper().strip()
    course = data['course'].upper().strip()
    category = data['category']
    gender = data['gender']

    # Check if the institute exists in the dataset
    if college not in newdata['NAME'].str.upper().values:
        return render_template('index.html', error=f"Error: The institute '{college}' is not found in the dataset.")

    # Filter data based on user inputs
    filtered_data = newdata[(
        newdata['NAME'].str.upper() == college) & 
        (newdata['COURSE'].str.upper() == course)
    ]

    # Filter by gender if specified
    if gender != 'none':
        filtered_data = filtered_data[filtered_data['GENDER'].str.upper() == gender.upper()]

    # Validate category input
    if category.lower() == 'none':
        plt.figure(figsize=(12, 6))
        sns.boxplot(x='CATEGORY', y='CLOSE RANK', data=filtered_data)
        plt.title('Box Plot of Closing Rank by Category')
        plt.xticks(rotation=90)
        plt.grid(True)

        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close()

        return send_file(img, mimetype='image/png')
    else:
        filtered_data = filtered_data[filtered_data['CATEGORY'].str.upper() == category.upper()]
        if filtered_data.empty:
            return render_template('index.html', error="No data found for the selected category.")

        filtered_data = filtered_data.sort_values(by='YEAR')
        plt.figure(figsize=(12, 6))
        plt.plot(filtered_data['YEAR'], filtered_data['CLOSE RANK'], linestyle='-', color='b', marker='o')
        plt.xlabel('Year')
        plt.ylabel('Closing Rank')
        plt.title(f'Closing Rank vs Year for {college} - {course} - {category}')
        plt.grid(True)

        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close()

        return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    app.run(host -"0.0.0.0",debug=True)

