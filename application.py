import os,bcrypt,requests
from dotenv import load_dotenv
from flask import Flask, session,render_template,request,redirect,url_for,jsonify,flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session,sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"),pool_size=20,max_overflow=0)
db = scoped_session(sessionmaker(bind=engine))

#GoodReads API Key
KEY=os.getenv("GOODREADS_KEY")

@app.route("/")
def home():
	if "user" in session:
		return redirect(url_for('loginhome'))
	return render_template("home.html")

@app.route("/login",methods=["POST","GET"])
def login():
	if request.method == "POST":
		username=request.form.get("username")
		password=request.form.get("password")
		password=password.encode('utf8')
		pass_get=db.execute("select password from users where username = :username",{"username":username}).fetchone()
		if pass_get and bcrypt.checkpw(password,pass_get[0].encode('utf8')):
			session["user"]=username
			flash("You have logged in")
			return redirect(url_for('loginhome'))
		else:
			return render_template("login.html",message="Incorrect Username or Password")
	if request.method == 'GET':
		if "user" in session:
			return redirect(url_for('loginhome'))
		return render_template("login.html")

@app.route("/signup",methods=["POST","GET"])
def signup():
	if request.method == "POST":
		username=request.form.get("username")
		password=request.form.get("password")
		password_hash=bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())
		password_hash=password_hash.decode('utf8')
		if db.execute("select username from users where username = :username",{"username":username}).rowcount == 0:
			db.execute("insert into users values(:username,:password)",{"username":username,"password":password_hash})
			db.commit()
			flash("You have registered")
			return redirect(url_for('home'))
		else:
			return render_template("signup.html",message="Username already taken")
	if request.method == 'GET':
		if "user" in session:
			return redirect(url_for('loginhome'))
		return render_template("signup.html")

@app.route("/login/home")
def loginhome():
	if "user" not in session:
		return redirect(url_for('home'))
	return render_template("login_home.html")

@app.route("/logout")
def logout():
	if "user" in session:
		session.pop("user",None)
		flash("You have logged out")
	return redirect(url_for('home'))

@app.route("/search",methods=["POST","GET"])
def search():
	if request.method == "GET":
		if "user" not in session:
			return redirect(url_for('home'))
		return render_template("search.html")
	else:
		value=request.form.get("book")
		search_query=request.form.get("search")
		return redirect(url_for('results',search_name=search_query,value=value))

@app.route("/search/<string:value>-<string:search_name>")
def results(search_name,value):
	if "user" not in session:
		return redirect(url_for('home'))
	if value == "isbn":
		res=db.execute("select * from books where isbn ilike Concat('%',:isbn,'%') order by isbn,title,author,pubyear limit 40 ",{"isbn":search_name}).fetchall()
	elif value == "title":
		res=db.execute("select * from books where title ilike Concat('%',:title,'%') order by title,author,pubyear,isbn limit 40",{"title":search_name}).fetchall()
	else:
		res=db.execute("select * from books where author ilike Concat('%',:author,'%') order by author,title,pubyear,isbn limit 40",{"author":search_name}).fetchall()
	return render_template("results.html",res=res)

@app.route("/<string:book_title>_<string:book_isbn>",methods=["POST","GET"])
def book_inform(book_title,book_isbn):
	if request.method =="GET":
		if "user" not in session:
			return redirect(url_for('home'))
		inform=db.execute("select isbn,title,author,pubyear,round(avg(rating),2) as avg_rating,count(rating) as count_rating from books left join reviews using(isbn) where isbn = :isbn group by isbn",{"isbn":book_isbn}).fetchone()
		res= requests.get("https://www.goodreads.com/book/review_counts.json", params={"key":KEY, "isbns":book_isbn})
		if res.status_code == 404:
			goodreads_inform=None
		else:
			goodreads_inform=res.json()["books"]
		reviews=db.execute("select * from reviews where isbn = :isbn",{"isbn":book_isbn}).fetchall()
		return render_template("book_inform.html",inform=inform,goodreads_inform=goodreads_inform,reviews=reviews)
	else:
		username_get=session["user"]
		if db.execute("select * from reviews where isbn = :isbn and username = :username ",{"username":username_get,"isbn":book_isbn}).rowcount != 0:
			return render_template("review_submitted.html")
		rev=request.form.get("review")
		rating_value=request.form.get("rating")
		db.execute("insert into reviews values(:username,:isbn,:review,:rating)",{"username":username_get,"isbn":book_isbn,"review":rev,"rating":rating_value})
		db.commit()
		return redirect(url_for('book_inform',book_title=book_title,book_isbn=book_isbn))

@app.errorhandler(404)
def page_not_found(error):
   return render_template('404.html'),404

@app.route("/api/<string:book_isbn>")
def api_get(book_isbn):
	book=db.execute("select isbn,title,author,pubyear,round(avg(rating),2) as avg_rating,count(rating) as count_rating from books left join reviews using(isbn) where isbn = :isbn group by isbn",{"isbn":book_isbn}).fetchone()
	if book is None:
		return render_template('404.html'),404
	else:
		avg_rating=book.avg_rating
		if avg_rating is None:
			avg_rating=0.0
		avg_rating=float(avg_rating)
		return jsonify(title=book.title,author=book.author,year=book.pubyear,isbn=book.isbn,review_count=book.count_rating,average_score=avg_rating)