import numpy as np
import pickle

from konlpy.tag import Okt
from scipy.sparse import lil_matrix
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression

pos_tagger = Okt()
# print(pos_tagger.nouns('한국어 분석을 시작합니다'))
# print(pos_tagger.morphs('한국어 분석을 시작합니다'))
# print(pos_tagger.pos('한국어 분석을 시작합니다'))

"""
Req 1-1-1. 데이터 읽기
read_data(): 데이터를 읽어서 저장하는 함수
"""

def read_data(filename):
    data = []
    with open(filename, 'r',encoding='UTF-8') as f:
        for line in f:
            if line.startswith("i"):
                continue
            else:
                temp = line.split('\t')
                data += [temp]
        return data


"""
Req 1-1-2. 토큰화 함수
tokenize(): 텍스트 데이터를 받아 KoNLPy의 okt 형태소 분석기로 토크나이징
"""

def tokenize(doc):
    total_pos = []
    for sentence in doc:
        check_sentence = sentence[1]
        result = ['/'.join(t) for t in pos_tagger.pos(check_sentence, norm=True, stem=True)]
        total_pos += [result]
            
    return total_pos


"""
데이터 전 처리
"""

# train, test 데이터 읽기
train_data = read_data('ratings_train.txt')
test_data = read_data('ratings_test.txt')


# Req 1-1-2. 문장 데이터 토큰화
# train_docs, test_docs : 토큰화된 트레이닝, 테스트  문장에 label 정보를 추가한 list
train_docs = tokenize(train_data)
test_docs = tokenize(test_data)


# Req 1-1-3. word_indices 초기화

word_indices = {}

# Req 1-1-3. word_indices 채우기
idx = 0
for part in train_docs:
    for k in part:
        meaning = k.split('/')[0]
        if word_indices.get(meaning)==None:
            word_indices[meaning]=idx
            idx+=1
    
# print(word_indices)

# Req 1-1-4. sparse matrix 초기화
# X: train feature data
# X_test: test feature data
X = lil_matrix((len(train_docs), len(word_indices)))
X_test = lil_matrix((len(test_docs), len(word_indices)))


# 평점 label 데이터가 저장될 Y 행렬 초기화
# Y: train data label
# Y_test: test data label
Y = np.zeros((len(train_docs),1))
Y_test = np.zeros((len(test_docs),1))

# Req 1-1-5. one-hot 임베딩
# X,Y 벡터값 채우기

for idx in range(len(train_docs)):
    temp = [0]*len(word_indices)
    for verb in train_docs[idx]:
        part = verb.split('/')[0]
        temp[word_indices[part]]=1
    X[idx]=temp


for idx in range(len(test_docs)):
    temp = [0]*len(word_indices)
    for verb in test_docs[idx]:
        part = verb.split('/')[0]
        if word_indices.get(part)!=None:
            temp[word_indices[part]]=1
    X_test[idx]=temp

for idx in range(len(train_data)):
    part = train_data[idx][2].split('\n')[0]
    Y[idx]=part


for idx in range(len(test_data)):
    part = test_data[idx][2].split('\n')[0]
    Y_test[idx]=part

