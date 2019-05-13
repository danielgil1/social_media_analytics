import couchdb
from flask import Flask, jsonify, make_response, render_template
from flask_cors import CORS, cross_origin
from collections import Counter, defaultdict
import copy
import pandas as pd
app = Flask(__name__)

cors = CORS(app, resources={r"/foo": {"origins": "http://localhost:port"}})




state = {
 'new south wales': 1,
 'victoria': 2,
 'queensland': 3,
 'south australia': 4,
 'western australia': 5, 
 'tasmania': 6, 
 'northern territory': 7,
 'australian capital territory': 8
}


user = "admin"
password = "p01ss0n"
couch_server = couchdb.Server("http://%s:%s@172.26.37.219:5984/" % (user, password))
db = couch_server['twitter']

ip = "http://admin:p01ss0n@172.26.37.219:5984/"
tweeter_db = 'twitter'
aurin_data_location = 'csv_files/vote_2016.csv'

@app.route('/')
def render_static():
    return render_template('index.html')


@app.route("/scenario_1_1/", methods=['GET'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def scenario_1_1():
    df = scenario_1_get_combined_distribution_twitter_aurin(ip, tweeter_db, aurin_data_location)
    result = {}
    for index, row in df.iterrows():
        result[row['state']] = [row['percent_votes'],row['percent_tweets']]

    return jsonify(result)



@app.route("/scenario_1_2/", methods=['GET'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def scenario_1_2():
    df1, df2 = scenerio_2_popularity_of_party_in_state_vs_aurion(ip,tweeter_db,aurin_data_location)
    result = {}
    temp = {}
    for index, row in df1.iterrows():
        temp[row['party']] = {}
    for key in state.keys():
        result[state[key]] = copy.deepcopy(temp)
    for index, row in df1.iterrows():
        for key in state.keys():
            result[state[key]][row['party']][0] = row[key]
    for index, row in df2.iterrows():
        for key in state.keys():
            result[state[key]][row['party']][1] = row[key]
    for key in state.keys():
        df3 = scenerio_3_tweet_sentiment(ip,tweeter_db, key)
        for index, row in df3.iterrows():
            result[state[key]][row['party']][2] = row['Positive']
            result[state[key]][row['party']][3] = row['Negative'] 
            result[state[key]][row['party']][4] = row['Neutral']
    return jsonify(result)

@app.route("/initial/", methods=['GET'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def hello():
    view = db.view('_design/counts/_view/location_state', reduce=True, group=True)
    count = Counter()

    for item in view:
        if item.key:
            key = item.key
            count[key] += item.value
    result = {}
    for key in state.keys():
        result[key] = count[key]
    return jsonify(result)


@app.route("/state/", methods=['GET'])
@cross_origin(origin='localhost',headers=['Content- Type','Authorization'])
def state_total_count():
    
    view = db.view('_design/counts/_view/location_state', reduce=True, group=True)
    count = Counter()

    for item in view:
        if item.key:
            key = item.key
            count[key] += item.value
    result = {}
    for key in state.keys():
        result[state[key]] = count[key]

    return jsonify(result)



def scenario_1_get_combined_distribution_twitter_aurin(ip,tweeter_db,aurin_data_location):
    
    # **********fetching data from couchdb**********
    couch_server = couchdb.Server(ip)
    db = couch_server[tweeter_db]
    view = db.view('_design/counts/_view/party_in_states', reduce=True, group=True)
    rows = []
    rows2 = []
    for item in view:
        key = item.key
        state = str(key[0])
        party = str(key[1])
        value = item.value
        if(party == "Liberal Democratic Party" or party == "Liberal National Party" or
           party == "Liberal Party of Australia"):
            if(state.islower()):
                rows2.append({'party': 'Liberal Party of Australia', 'state':state, 'tweet_mentions':value})
        else:
            if(state.islower()):
                rows.append({'party': party, 'state':state, 'tweet_mentions':value})

    # **********Twitter data dataframe creating**********
    
    df_twitter_party = pd.DataFrame(rows)
    df_twitter_party = pd.concat([df_twitter_party, pd.DataFrame(rows2).groupby(['party','state']).sum().reset_index()])
    df_twitter_party = pd.pivot_table(df_twitter_party,values='tweet_mentions',index=['state'],
                                      columns=['party']).reset_index()
    df_twitter_party = df_twitter_party.fillna(0)
    df_twitter_party.loc[:,'total_tweets'] = df_twitter_party.sum(axis=1)
    columns = ["state","Australian Labor Party", "Liberal Party of Australia", "Australian Greens",
               "United Australia Party","total_tweets"]
    df_twitter_party = df_twitter_party[columns]
    
    # **********Voting data dataframe creating**********
    
    df_vote = pd.read_csv(aurin_data_location)
    df_vote = df_vote.rename(columns=lambda x: x.strip())
    df_vote = df_vote.rename(columns = {'divisionnm':'seat'})
    df_vote = df_vote[['alp_votes','alp_tpp_votes', 'coa_votes','coa_tpp_votes', 'grn_votes','on_votes',
                       'total_votes','seat']]
    df_vote = df_vote.rename(columns = {'alp_votes':'Australian Labor Party',
                                        'alp_tpp_votes':'Australian Labor Party (TPP)',
                                        'coa_votes': 'Liberal Party of Australia',
                                        'coa_tpp_votes':'Liberal Party of Australia (TPP)',
                                        'grn_votes': 'Australian Greens',
                                        'on_votes': 'United Australia Party'})

    df_vote = pd.merge(df_vote,pd.read_csv('csv_files/aurin_location.csv')[['seat','city','state']], on='seat')
    df_vote = df_vote.fillna(0)
    df_vote['state'] = df_vote['state'].str.lower()
    df_vote['seat'] = df_vote['seat'].str.lower()
    df_vote['city'] = df_vote['city'].str.lower()
    df_vote = pd.DataFrame(df_vote.groupby('state').sum())
    df_vote = df_vote.reset_index()
    columns = ["state","Australian Labor Party", "Liberal Party of Australia", "Australian Greens",
               "United Australia Party","total_votes"]
    df_vote = df_vote[columns]
    
    # ********** Combining two dataframe by state and calculating percentage**********
    df_combined = pd.merge(df_vote,df_twitter_party, on =['state'])
    df_combined['percent_tweets']= df_combined['total_tweets']/df_combined['total_tweets'].sum()
    df_combined['percent_votes']= df_combined['total_votes']/df_combined['total_votes'].sum()
    df_combined['labor_vote']= df_combined['Australian Labor Party_x']/df_combined['Australian Labor Party_x'].sum()
    df_combined['labor_twitter']= df_combined['Australian Labor Party_y']/df_combined['Australian Labor Party_y'].sum()
    df_combined['liberal_vote']= df_combined['Liberal Party of Australia_x']/df_combined['Liberal Party of Australia_x'].sum()
    df_combined['liberal_twitter']= df_combined['Liberal Party of Australia_y']/df_combined['Liberal Party of Australia_y'].sum()
    df_combined['united_vote']= df_combined['United Australia Party_x']/df_combined['United Australia Party_x'].sum()
    df_combined['united_twitter']= df_combined['United Australia Party_y']/df_combined['United Australia Party_y'].sum()
    df_combined['greens_vote']= df_combined['Australian Greens_x']/df_combined['Australian Greens_x'].sum()
    df_combined['greens_twitter']= df_combined['Australian Greens_y']/df_combined['Australian Greens_y'].sum()
    
    df_combined = df_combined[['state','percent_votes','percent_tweets','labor_vote','labor_twitter',
             'liberal_vote','liberal_twitter','united_vote','united_twitter',
            'greens_vote','greens_twitter']].round(4)
    
    return df_combined

def scenerio_2_popularity_of_party_in_state_vs_aurion(ip,tweeter_db,aurin_data_location):
    
    # **********fetching data from couchdb**********
    couch_server = couchdb.Server(ip)
    db = couch_server[tweeter_db]
    view = db.view('_design/counts/_view/party_in_states', reduce=True, group=True)
    rows = []
    rows2 = []

    for item in view:
        key = item.key
        state = str(key[0])
        party = str(key[1])
        value = item.value
        if(party == "Liberal Democratic Party" or party == "Liberal National Party" or
           party == "Liberal Party of Australia"):
            if(state.islower()):
                rows2.append({'party': 'Liberal Party of Australia', 'state':state, 'tweet_mentions':value})
        else:
            if(state.islower()):
                rows.append({'party': party, 'state':state, 'tweet_mentions':value})
    
    # **********Twitter data dataframe creating**********
    
    df_twitter_party = pd.DataFrame(rows)
    df_twitter_party = pd.concat([df_twitter_party, pd.DataFrame(rows2).groupby(['party','state']).sum().reset_index()])


    df_twitter_party = pd.pivot_table(df_twitter_party,values='tweet_mentions',index=['state'],
                                      columns=['party'])

    df_twitter_party = df_twitter_party.fillna(0)
    df_twitter_party.loc[:,'total_tweets_state'] = df_twitter_party.sum(axis=1)
    df_twitter_party = df_twitter_party.div(df_twitter_party['total_tweets_state'].values,axis=0).reset_index()

    df_twitter_party = df_twitter_party.set_index('state').transpose()
    df_twitter_party = df_twitter_party.reset_index()
    df_twitter_party = df_twitter_party.rename(columns = {'index':'party'})

    df_twitter_party = df_twitter_party.reset_index().round(4)
    df_twitter_party = df_twitter_party[(df_twitter_party['party'] == "Australian Labor Party") | 
                     (df_twitter_party['party'] == "Liberal Party of Australia") |
                     (df_twitter_party['party'] == "Australian Greens") |
                     (df_twitter_party['party'] == "United Australia Party")]
    df_twitter_party = df_twitter_party.drop(columns = ['index'])
    
    
    df_vote = pd.read_csv(aurin_data_location)
    df_vote = df_vote.rename(columns=lambda x: x.strip())
    df_vote = df_vote.rename(columns = {'divisionnm':'seat'})
    df_vote = df_vote[['alp_votes','alp_tpp_votes', 'coa_votes','coa_tpp_votes', 'grn_votes','on_votes',
                       'total_votes','seat']]
    df_vote = df_vote.rename(columns = {'alp_votes':'Australian Labor Party',
                                        'alp_tpp_votes':'Australian Labor Party (TPP)',
                                        'coa_votes': 'Liberal Party of Australia',
                                        'coa_tpp_votes':'Liberal Party of Australia (TPP)',
                                        'grn_votes': 'Australian Greens',
                                        'on_votes': 'United Australia Party'})

    
    # **********Voting data dataframe creating**********
    
    df_vote = pd.merge(df_vote,pd.read_csv('csv_files/aurin_location.csv')[['seat','city','state']], on='seat')
    df_vote = df_vote.fillna(0)
    df_vote['state'] = df_vote['state'].str.lower()
    df_vote['seat'] = df_vote['seat'].str.lower()
    df_vote['city'] = df_vote['city'].str.lower()
    df_vote = pd.DataFrame(df_vote.groupby('state').sum())
    df_vote = df_vote.div(df_vote['total_votes'].values,axis=0).reset_index()

    df_vote = df_vote.set_index('state').transpose()
    df_vote = df_vote.reset_index()
    df_vote = df_vote.rename(columns = {'index':'party'})

    df_vote = df_vote[(df_vote['party'] == "Australian Labor Party") | 
            (df_vote['party'] == "Liberal Party of Australia") |
            (df_vote['party'] == "Australian Greens") |
            (df_vote['party'] == "United Australia Party")]

    df_vote = df_vote.reset_index().round(4)
    df_vote = df_vote.drop(columns = ['index'])
    
    return df_twitter_party, df_vote

def scenerio_3_tweet_sentiment(ip,tweeter_db, state_name):
    
    # **********fetching data from couchdb**********
    couch_server = couchdb.Server(ip)
    db = couch_server[tweeter_db]
    view = db.view('_design/counts/_view/sentiment_party', reduce=True, group=True)

    rows = []
    rows2 = []
    for item in view:
        key = item.key
        party = str(key[0])
        sentiment = str(key[1])
        intensity = str(key[2])
        city = str(key[3])
        state = str(key[4])
        count = item.value
        if(party == "Liberal Democratic Party" or party == "Liberal National Party" or
           party == "Liberal Party of Australia"):
            if(state.islower()):
                rows2.append({'party': 'Liberal Party of Australia', 'sentiment': sentiment,
                              'intensity': intensity, 'city': city, 'state' :state, 'count': count})
        else:
            if(state.islower()):
                rows.append({'party': party, 'sentiment': sentiment, 'intensity': intensity, 'city': city,
                             'state' :state, 'count': count})

    # **********Twitter data dataframe creating**********
    
    df_twitter_sentiment = pd.DataFrame(rows)
    df_twitter_sentiment = pd.concat([df_twitter_sentiment, pd.DataFrame(rows2)])
    df_twitter_sentiment = df_twitter_sentiment[df_twitter_sentiment['state'] == state_name]
    df_twitter_sentiment = df_twitter_sentiment[(df_twitter_sentiment['party'] == "Australian Labor Party") | 
                         (df_twitter_sentiment['party'] == "Liberal Party of Australia") |
                         (df_twitter_sentiment['party'] == "Australian Greens") |
                         (df_twitter_sentiment['party'] == "United Australia Party")]
    df_twitter_sentiment = df_twitter_sentiment.drop(columns = ['city','intensity','state'], axis = 1)
    df_twitter_sentiment = df_twitter_sentiment.groupby(['party','sentiment']).sum().reset_index()

    df_twitter_sentiment = pd.pivot_table(df_twitter_sentiment,values='count',index=['party'],
                                          columns=['sentiment'])
    df_twitter_sentiment = df_twitter_sentiment.div(df_twitter_sentiment.sum(axis=1), axis=0).round(2).reset_index()
    
    return df_twitter_sentiment


if __name__ == '__main__':
    app.run()