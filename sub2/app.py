import numpy as np
import json
import pickle
import sqlite3
import requests

from konlpy.tag import Okt
from scipy.sparse import lil_matrix
from sklearn.naive_bayes import MultinomialNB
from sklearn import linear_model

from flask import Flask, request, make_response, Response
from slack import WebClient
from slackeventsapi import SlackEventAdapter

from retrain import read_data, tokenize

# slack 연동 정보 입력 부분
SLACK_TOKEN = "xoxb-720220358483-738701955364-q3tCkTnPKzSFEQbW2a8vnrWm"
SLACK_SIGNING_SECRET = "61d52b36a564138f59046147325dcfe4"

app = Flask(__name__)

slack_events_adaptor = SlackEventAdapter(SLACK_SIGNING_SECRET, "/listening", app)
slack_web_client = WebClient(token=SLACK_TOKEN)

# Req 2-2-1. pickle로 저장된 model.clf 파일 불러오기
pickle_obj = open('origin_model.clf', 'rb')
NB = pickle.load(pickle_obj) # naive bayes
LR = pickle.load(pickle_obj) # Logistic Regression
SVM = pickle.load(pickle_obj) # SVM
DT = pickle.load(pickle_obj) # 의사결정트리
word_indices = pickle.load(pickle_obj)

neg = 0
pos = 0
msg = ""

output = -1  # 트레이닝결과값 0/1을 db에 쓰기위한 초기화 변수
beforeTrainDataIdx = 0 

# Req 2-2-2. 토큰화 및 one-hot 임베딩하는 전 처리
pos_tagger = Okt()

def preprocess(sentence, word_indices):
    # 토큰화
    Word_vector = []
    result = ['/'.join(t) for t in pos_tagger.pos(sentence, norm=True, stem=True)]
    Word_vector += [result]

    # one-hot 임베딩
    for idx in range(len(Word_vector)):
        temp = [0]*len(word_indices)
        for morph in Word_vector[idx]:
            word = morph.split('/')[0]
            if word_indices.get(word) != None:
                temp[word_indices[word]] = 1
        Word_vector[idx] = temp

    return Word_vector

def predict(Word_vector, test_clf):
    predict_result = test_clf.predict(Word_vector)[0]
    return predict_result

# # Req 2-2-3. 긍정 혹은 부정으로 분류
def classify(sentence, test_clf, model_name):
    global neg
    global pos
    
    weight = [0.3, 0.7]

    predict_result = int(predict(sentence, test_clf))

    if model_name=="NB" or model_name=="DT":
        neg += test_clf.predict_proba(sentence)[0][0]
        pos += test_clf.predict_proba(sentence)[0][1]

    else:
        neg += weight[1-predict_result]
        pos += weight[predict_result]
    
    return "positive" if predict_result else "negative"

def send_message(sentence, ch):
    global neg, pos
    global output

    Word_vector = preprocess(sentence.split("> ")[1], word_indices)
    predict_NB = classify(Word_vector, NB, "NB")
    predict_LR = classify(Word_vector, LR, "LR")
    predict_SVM = classify(Word_vector, SVM, "SVM")
    predict_DT = classify(Word_vector, DT, "DT")

    if neg > pos:
        result = "negative"
        img = "https://imgur.com/L3ZrqYS.gif"
        output = 0
    else:
        result = "positive"
        img = "https://imgur.com/oLCYpsU.gif"
        output = 1

    neg = 0
    pos = 0

    attachement = {
            "color": "#fe6f5e",
            "image_url": img,
            "title": "RESULT",
            'pretext': sentence.split("> ")[1],
            "fallback": "Status Monitor",
            "callback_id": "button_event",
            "text": result,
            "fields":[
                {
                    "title": "Naive Baysian model",
                    "value": predict_NB,
                    "short": True
                },
                {
                    "title": "Logistic Regresion model",
                    "value": predict_LR,
                    "short": True
                },
                {
                    "title": "Support Vector Machine model",
                    "value": predict_SVM,
                    "short": True
                },
                {
                    "title": "Decision Tree Classifier model",
                    "value": predict_DT,
                    "short": True
                }
            ],
            "actions": [
                {
                    "name": "edit",
                    "text": "EDIT",
                    "type": "button",
                    "value": "edit",
                    "style": "danger"
                },
                {
                    "name": "trainig",
                    "text": "TRAINING",
                    "type": "button",
                    "value": "training",
                    "style": "danger"
                },
                {
                    "name": "naver",
                    "text": "NAVER SHOW",
                    "type": "button",
                    "value": "naver",
                    "style": "danger"
                }
            ],
        }
    slack_web_client.chat_postMessage(
        channel=ch,
        text=None,
        attachments=[attachement],
        as_user=False)

# 네이버 데이터 셋 결과
def send_naver_message(ch):
    global neg, pos
    global msg

    pickle_obj = open('naver_model.clf', 'rb')
    naver_NB = pickle.load(pickle_obj) # naive bayes
    naver_LR = pickle.load(pickle_obj) # Logistic Regression
    naver_SVM = pickle.load(pickle_obj) # SVM
    naver_DT = pickle.load(pickle_obj) # 의사결정트리
    naver_word_indices = pickle.load(pickle_obj)

    test_doc = preprocess(msg.split("> ")[1], naver_word_indices)
    predict_NB = classify(test_doc, naver_NB, "NB")
    predict_LR = classify(test_doc, naver_LR, "LR")
    predict_SVM = classify(test_doc, naver_SVM, "SVM")
    predict_DT = classify(test_doc, naver_DT, "DT")
    
    if neg > pos:
        result = "negative"
        img = "https://i.pinimg.com/originals/2c/21/8f/2c218fa1247ce35d20cb618e9f3049d4.gif"
    else:
        result = "positive"
        img = "https://img1.daumcdn.net/thumb/R800x0/?scode=mtistory2&fname=https%3A%2F%2Ft1.daumcdn.net%2Fcfile%2Ftistory%2F99A4654C5C63B09028"

    neg = 0
    pos = 0

    attachement = {
            "color": "#fe6f5e",
            "title": "NAVER RESULT",
            'pretext': msg.split("> ")[1],
            "fallback": "Status Monitor",
            "callback_id": "button_event",
            "text": result,
            "fields":[
                {
                    "title": "Naive Baysian model",
                    "value": predict_NB,
                    "short": True
                },
                {
                    "title": "Logistic Regresion model",
                    "value": predict_LR,
                    "short": True
                },
                {
                    "title": "Support Vector Machine model",
                    "value": predict_SVM,
                    "short": True
                },
                {
                    "title": "Decision Tree Classifier model",
                    "value": predict_DT,
                    "short": True
                }
            ],
        }
    slack_web_client.chat_postMessage(
        channel=ch,
        text=None,
        attachments=[attachement],
        as_user=False)

# # Req 2-2-4. app.db 를 연동하여 웹에서 주고받는 데이터를 DB로 저장
def save_text_to_db(sentence):
    # db에 저장
    global output

    con = sqlite3.connect('./app.db')
    cur = con.cursor()

    msg = sentence.split("> ")[1]
    cur.execute(
        'INSERT INTO search_history(question, answer) VALUES(?,?)', (msg, output,))
    con.commit()

    output = -1
    cur.close()

# 결과값이 틀린 경우 데이터를 DB에 저장
def edit_data():
    chk = False
    con = sqlite3.connect('./app.db')
    cur = con.cursor()

    recent_record = cur.execute(
        'SELECT max(id), answer FROM search_history')
    idx = 0
    answer = -1
    for value in recent_record:
        idx = value[0]
        answer = value[1]

    if(answer == 0):
        cur.execute('UPDATE search_history SET answer = 1 WHERE id = %s' % idx)
        print("1로 수정완료")
        chk = True
    elif(answer == 1):
        cur.execute('UPDATE search_history SET answer = 0 WHERE id = %s ' % idx)
        print("0으로 수정완료")
        chk = True
    else:
        print("error")

    con.commit()
    cur.close()

    # db 업데이트 성공유무를 리턴
    return chk

# 추가 데이터 트레이닝
def data_training():
    global beforeTrainDataIdx
    chk = True

    con = sqlite3.connect('./app.db')
    cur = con.cursor()
    # DB에 저장된 데이터 개수 확인
    recent_record = cur.execute(
        'SELECT max(id), answer FROM search_history')

    recent_idx = 0
    for value in recent_record:
        recent_idx = value[0]

    # DB에 데이터가 10개 미만일 경우 chk -> false
    if((recent_idx - beforeTrainDataIdx) < 10):
        print("추가로 저장된 데이터가 10개 미만입니다")
        chk = False

    # DB에 데이터가 10개 이상일 경우 chk -> true
    else:
        print("학습하겠습니다")
        print("{}부터 학습합니다".format(beforeTrainDataIdx+1))

        f = open('retrain.txt', mode='wt', encoding='utf-8')
        readData = cur.execute(
            'SELECT * FROM search_history WHERE id > %s ' % beforeTrainDataIdx
        )
        temp = ""
        for data in readData:
            row = str(data[1]) + "\t" + data[2] + "\t" + str(data[3]) + "\n"
            temp += row

        f.write(temp)
        print("트레이닝 파일 쓰기완료")
        f.close()

        beforeTrainDataIdx = recent_idx  
        print("{} idx 까지 학습완료".format(beforeTrainDataIdx))
        chk = True
        
        # 추가 데이터 트레이닝
        train_data = read_data('retrain.txt')
        train_docs = tokenize(train_data)
        print('read_data, tokenize')

        X = lil_matrix((len(train_docs), len(word_indices)))
        Y = np.zeros(len(train_docs))

        print('X, Y init')
        for idx in range(len(train_docs)):
            temp = [0]*len(word_indices)
            for morph in train_docs[idx]:
                word = morph.split('/')[0]
                if word_indices.get(word)!=None:
                    temp[word_indices[word]]=1
            X[idx]=temp
        print('X one hot embedding ')
        for idx in range(len(train_data)):
            part = train_data[idx][2].split('\n')[0]
            Y[idx]=part
        print('Y label')
        NB.partial_fit(X, Y) # naive Bayes
        print('naive')
        LR.partial_fit(X, Y) # Logistic
        print('logistic')
        SVM.partial_fit(X, Y) # SVM
        print('SVM')

        fl = open('origin_model.clf', 'wb')
        pickle.dump(NB, fl)
        pickle.dump(LR, fl)
        pickle.dump(SVM, fl)
        pickle.dump(DT, fl)
        pickle.dump(word_indices, fl)
        fl.close()

    cur.close()
   
    return chk


@app.route("/", methods=["GET"])
def index():
    return "<h1>Server is ready.</h1>"

# 챗봇이 멘션을 받았을 경우
@slack_events_adaptor.on("app_mention")
def app_mentioned(event_data):
    global msg
    retry_count = request.headers.get("x-slack-retry-num")
    
    if retry_count:
        return make_response('No', 200, {"X-Slack-No-Retry": 1})
    else:
        channel = event_data["event"]["channel"]
        sentence = event_data["event"]["text"]
        msg = sentence
        # 메세지 보내기
        send_message(sentence, channel)
        # DB에 데이터 저장
        save_text_to_db(sentence)
    return make_response('No', 200, {"X-Slack-No-Retry": 1})
    

@app.route("/click", methods=["GET", "POST"])
def on_button_click():
    payload = request.values["payload"]
    clicked = json.loads(payload)["actions"][0]['value']
    my_ch = json.loads(payload)["channel"]["id"]
    print(clicked)
    if clicked == "edit":
        print("edit")
        edit_data()
    elif clicked == "training":
        print("train")
        if data_training():
            print("Success Training")
        else:
            clicked = "추가 데이터가 부족합니다. 문장을 더 입력해주세요"
            print("Save more Data")
    else:
        print("naver start")
        send_naver_message(my_ch)
        print("sending naver")
        return make_response("", 200)

    slack_web_client.chat_postMessage(
        channel=my_ch,
        text=clicked
    )
    return make_response("", 200)


if __name__ == '__main__':
    app.run(host='172.26.8.106')
   
