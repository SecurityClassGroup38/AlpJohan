import json, sqlite3, click, functools, os, hashlib, time, secrets, sys, io, re, zipfile
from flask import Flask, current_app, g, session, redirect, render_template, url_for, request, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

### DATABASE FUNCTIONS ###

def connect_db():
    return sqlite3.connect(app.database)

def init_db():
    """Initializes the database with our great SQL schema"""
    conn = connect_db()
    db = conn.cursor()
    db.executescript("""

DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS notes;

CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assocUser INTEGER NOT NULL,
    author TEXT NOT NULL,
    dateWritten DATETIME NOT NULL,
    note TEXT NOT NULL,
    publicID INTEGER NOT NULL,
    public INTEGER NOT NULL DEFAULT 0,
    imported INTEGER NOT NULL DEFAULT 0,
    imagePath TEXT NOT NULL DEFAULT ''
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL
);

""")


### APPLICATION SETUP ###
app = Flask(__name__)
app.database = "db.sqlite3"
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif"}

def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT

app.secret_key = os.urandom(32) ## might be a vulnerability

### ADMINISTRATOR'S PANEL ###
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.route("/")
def index():
    if not session.get('logged_in'):
        return render_template('index.html')
    else:
        return redirect(url_for('notes'))

# notes page
@app.route("/notes/", methods=('GET', 'POST'))
@login_required
def notes():
    importerror=""

    def newNotePublicID(c):
        while True:
            id = secrets.randbelow(9000000000) + 1000000000
            c.execute("SELECT 1 FROM notes WHERE publicID = ?", (id,))
            if c.fetchone() is None:
                return id

    #Posting a new note:
    if request.method == 'POST':
        if request.form['submit_button'] == 'add note':
            note = request.form['noteinput']

            # optional image upload (SAFE: cleaned filename + type check only)
            imagepath = ""
            file = request.files.get('noteimage')
            if file and file.filename != "" and allowed_image(file.filename):
                safename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, safename))
                imagepath = "/static/uploads/" + safename

            db = connect_db()
            c = db.cursor()
            statement = """INSERT INTO notes (id, assocUser, author, dateWritten, note, publicID, imagePath)
                   VALUES (NULL, ?, ?, ?, ?, ?, ?)"""
            params = (
                session['userid'],
                session['username'],
                time.strftime('%Y-%m-%d %H:%M:%S'),
                note,
                newNotePublicID(c),
                imagepath,
            )
            c.execute(statement, params)
            db.commit()
            db.close()

        elif request.form['submit_button'] == 'import note':
            noteid = request.form['noteid']
            db = connect_db()
            c = db.cursor()
            statement = """SELECT * from NOTES where publicID = ?"""
            params = (noteid,)
            c.execute(statement, params)
            result = c.fetchall()
            if(len(result)>0):
                row = result[0]
                statement = """INSERT INTO notes(id,assocUser,author,dateWritten,note,publicID,imported)
               VALUES(null,?,?,?,?,?,1);"""
                params = (
                    session['userid'],
                    row[2],
                    row[3],
                    row[4],
                    row[5],)
                c.execute(statement, params)
            else:
                importerror="No such note with that ID!"
            db.commit()
            db.close()

        elif request.form['submit_button'] == 'delete note':
            noteid = request.form['noteid']
            db = connect_db()
            c = db.cursor()
            # SAFE: parameterized, not injectable. Only deletes YOUR own note.
            statement = "DELETE FROM notes WHERE publicID = ? AND assocUser = ?"
            params = (noteid, session['userid'])
            c.execute(statement, params)
            db.commit()
            db.close()

        elif request.form['submit_button'] == 'download zip':
            raw = request.form.get('zipname', 'notes')
            safe_name = re.sub(r'[^A-Za-z0-9_-]', '', raw)[:50]
            if not safe_name:
                safe_name = 'notes'

            db = connect_db()
            c = db.cursor()
            c.execute("SELECT * FROM notes WHERE assocUser = ?;", (session['userid'],))
            user_notes = c.fetchall()
            db.close()

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for n in user_notes:
                    zf.writestr(f"note_{n[0]}.txt", str(n[4]))
            buffer.seek(0)

            return send_file(buffer, mimetype='application/zip',
                             as_attachment=True, download_name=f"{safe_name}.zip")

    db = connect_db()
    c = db.cursor()
    statement = "SELECT * FROM notes WHERE assocUser = ?;"
    params = (session['userid'],)
    c.execute(statement, params)
    notes = c.fetchall()
    print(notes)
    return render_template('notes.html',notes=notes,importerror=importerror)


@app.route("/login/", methods=('GET', 'POST'))
def login():
    error = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = connect_db()
        c = db.cursor()
        statement = "SELECT * FROM users WHERE username = ?;"
        params = (username,)
        c.execute(statement, params)
        result = c.fetchall()
        if(len(result)!= 0):
            stored_hash = result[0][2]
            if check_password_hash(stored_hash, password):
                session.clear()
                session['logged_in'] = True
                session['userid'] = result[0][0]
                session['username']=result[0][1]
                return redirect(url_for('index'))
            else:
                error = "Wrong username or password!"
        else:
            error = "Wrong username or password!"
    return render_template('login.html',error=error)


@app.route("/register/", methods=('GET', 'POST'))
def register():
    errored = False
    usererror = ""
    passworderror = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = connect_db()
        c = db.cursor()
        user_statement = """SELECT * FROM users WHERE username = ?;"""
        params = (username,)

        if(len(password)<7):
            errored = True
            passworderror = "That password to weak, must be at least 7 characters!"

        c.execute(user_statement, params)
        if(len(c.fetchall())>0):
            errored = True
            usererror = "That username is already in use by someone else!"

        if(not errored):
            hashed_password = generate_password_hash(
                password,
                method="pbkdf2:sha256:600000"
            )
            statement = """INSERT INTO users(id,username,password) VALUES(null,?,?);"""
            params = (username, hashed_password,)
            c.execute(statement, params)
            db.commit()
            db.close()
            return f"""<html>
                        <head>
                            <meta http-equiv="refresh" content="2;url=/" />
                        </head>
                        <body>
                            <h1>SUCCESS!!! Redirecting in 2 seconds...</h1>
                        </body>
                        </html>
                        """
        db.commit()
        db.close()
    return render_template('register.html',usererror=usererror,passworderror=passworderror)


@app.route("/logout/")
@login_required
def logout():
    """Logout: clears the session"""
    session.clear()
    return redirect(url_for('index'))


@app.route("/reset/", methods=('GET', 'POST'))
def reset_password():
    usererror = ""
    emailerror = ""
    show_popup = False

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()

        db = connect_db()
        c = db.cursor()
        c.execute("SELECT 1 FROM users WHERE username = ?;", (username,))
        user_exists = c.fetchone() is not None
        db.close()

        if not user_exists:
            usererror = "No user with that username!"
        if "@" not in email:
            emailerror = "Please enter a valid email address."

        if not usererror and not emailerror:
            show_popup = True

    return render_template('reset.html', usererror=usererror,
                           emailerror=emailerror, show_popup=show_popup)


@app.route("/notes/<int:note_id>/toggle_public", methods=('POST',))
@login_required
def toggle_public(note_id):
    db = connect_db()
    c = db.cursor()
    c.execute(
        """UPDATE notes SET public = 1 - public
           WHERE id = ? AND assocUser = ? AND imported = 0;""",
        (note_id, session['userid']),
    )
    db.commit()
    db.close()
    return redirect(url_for('notes'))


@app.route("/feed/")
@login_required
def feed():
    db = connect_db()
    c = db.cursor()
    c.execute(
        """SELECT author, dateWritten, note, publicID FROM notes
           WHERE public = 1 ORDER BY dateWritten DESC;"""
    )
    feed_notes = c.fetchall()
    db.close()
    return render_template('feed.html', feed_notes=feed_notes)

if __name__ == "__main__":
    if not os.path.exists(app.database):
        init_db()
    runport = 5000
    if(len(sys.argv)==2):
        runport = sys.argv[1]
    try:
        app.run(host='0.0.0.0', port=runport)
    except:
        print("Something went wrong. the usage of the server is either")
        print("'python3 app.py' (to start on port 5000)")
        print("or")
        print("'sudo python3 app.py 80' (to run on any other port)")
