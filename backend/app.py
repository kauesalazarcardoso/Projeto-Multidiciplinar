from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

def conectar():
    return psycopg2.connect(
        host="db",
        database="acai",
        user="postgres",
        password="postgres"
    )

@app.route("/")
def home():
    return "Backend funcionando 🍧"

@app.route("/produtos")
def produtos():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM produtos;")
    dados = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(dados)

app.run(host="0.0.0.0", port=5000)