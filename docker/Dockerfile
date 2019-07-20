# FROM python:3 - not working with python 3.8 yet https://stackoverflow.com/questions/51265858/syntaxerror-generator-expression-must-be-parenthesized?answertab=votes#tab-top
FROM python:3.5.6

RUN apt-get update && apt-get -y install gettext && apt-get clean

WORKDIR /repanier

COPY requirements/requirement-2.0.txt /repanier/requirements/requirements.txt
RUN pip install -r requirements/requirements.txt

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
