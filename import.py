import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,scoped_session

engine=create_engine(os.getenv("DATABASE_URL"))

db=scoped_session(sessionmaker(bind=engine))

def main():
	file=open("books.csv")
	reader=csv.reader(file)
	for isbn,title,author,pubyear in reader:
		db.execute("insert into books values(:isbn,:title,:author,:pubyear)",{"isbn":isbn,"title":title,"author":author,"pubyear":pubyear})
	db.commit()

if __name__ == '__main__':
	main()
