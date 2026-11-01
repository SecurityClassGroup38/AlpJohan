import json, sqlite3, click, functools, os, hashlib,time, secrets, sys
from flask import Flask, current_app, g, session, redirect, render_template, url_for, request


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
    dateWritten DATETIME NOT NULL,
    note TEXT NOT NULL,
    publicID INTEGER NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL
);

INSERT INTO users VALUES(null,"admin", "password");
INSERT INTO users VALUES(null,"bernardo", "omgMPC");
INSERT INTO notes VALUES(null,2,"1993-09-23 10:10:10","hello my friend",1234567890);
INSERT INTO notes VALUES(null,2,"1993-09-23 12:10:10","i want lunch pls",1234567891);

""")



### APPLICATION SETUP ###
app = Flask(__name__)
app.database = "db.sqlite3"
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
    #Posting a new note:
    if request.method == 'POST':
        if request.form['submit_button'] == 'add note':
            note = request.form['noteinput']
            db = connect_db()
            c = db.cursor()
            # line 77 has sql injection vulnerability - FIXED
            # Possibility of duplicate IDs  
        
            statement = """INSERT INTO notes (id, assocUser, dateWritten, note, publicID)
                   VALUES (NULL, ?, ?, ?, ?)"""
            params = (
                session['userid'],
                time.strftime('%Y-%m-%d %H:%M:%S'),
                note,
                secrets.randbelow(9000000000) + 1000000000,
            )

            c.execute(statement, params)
            db.commit()
            db.close()
        elif request.form['submit_button'] == 'import note':
            noteid = request.form['noteid']
            db = connect_db()
            c = db.cursor()
            ## sql injection problem, can be used to run SELECT statements -FIXED
            statement = """SELECT * from NOTES where publicID = ?"""
            params = (noteid,)

            c.execute(statement, params)
            ## result is a list of lists
            result = c.fetchall()
            if(len(result)>0):
                # every user have a list of notes, and one note is a list by itself with the information fields about the note
        
                # row is a single list of the individual note
                # row is the first note with that searched noteid
                row = result[0]
                # Risk of SQL injection - FIXED
                statement = """INSERT INTO notes(id,assocUser,dateWritten,note,publicID) VALUES(null,?,?,?,?);""" 
                params = (session['userid'],row[2],row[3],row[4],)
                # when you import a note, its duplicated with the same date, noteid, and note fields are same
                # but userid is updated with importer 
                # so this 'if check' will get more than one outputs for noteid check, and only insert the first one
                # This creates an integrety problem, as the original author will be changed
                c.execute(statement, params)
            else:
                importerror="No such note with that ID!"
            db.commit()
            db.close()
    
    db = connect_db()
    c = db.cursor()
    # Runs when we open the page

    #SQL injection - FIXED
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
        # Allows for injection - FIXED 
        # password should be hashed (idea: concatinate username and password before hash, this will create unique hashes) 
        statement = "SELECT * FROM users WHERE username = ? AND password = ?;"
        params = (username, password,) 

        c.execute(statement, params)
        result = c.fetchall()

        if len(result) > 0:
            session.clear()
            # we are both using "logged in", "user ID", and "username" in a session, this can be redundant and possibly a risk (if loggedIn is not reset on logout)
            session['logged_in'] = True
            session['userid'] = result[0][0]
            session['username']=result[0][1]
            return redirect(url_for('index'))
        else:
            error = "Wrong username or password!"
    return render_template('login.html',error=error)


@app.route("/register/", methods=('GET', 'POST'))
def register():
    errored = False
    # get rid of password error (deos not have to be unique), however can be changed to enforce strong passwords
    usererror = ""
    passworderror = ""
    if request.method == 'POST':
        

        username = request.form['username']
        password = request.form['password']
        db = connect_db()
        c = db.cursor()
        # sanitize input, to avoid SQL injection - FIXED
        # delete passStatement + first if statement -FIXED
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
            # sanitize input to avoid SQL injection - FIXED
            # Password should be hashed before being inserted, make sure that password checks are alligned,
            statement = """INSERT INTO users(id,username,password) VALUES(null,?,?);"""
            params = (username, password,)

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

if __name__ == "__main__":
    #create database if it doesn't exist yet
    if not os.path.exists(app.database):
        init_db()
    runport = 5000
    if(len(sys.argv)==2):
        runport = sys.argv[1]
    try:
        app.run(host='0.0.0.0', port=runport) # runs on machine ip address to make it visible on netowrk
    except:
        print("Something went wrong. the usage of the server is either")
        print("'python3 app.py' (to start on port 5000)")
        print("or")
        print("'sudo python3 app.py 80' (to run on any other port)")