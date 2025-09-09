from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_file():
    return jsonify({"message": "Backend is working!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
