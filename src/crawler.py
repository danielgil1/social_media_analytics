import couchdb
import sys
import atexit
from harvesters import StreamTweetHarvester, KeywordsHarvester
from DB_Saver import Saving_Layer
import datetime
import pandas as pd
from mpi4py import MPI

COUCH_SERVER = couchdb.Server("http://admin:p01ss0n@103.6.254.96:9584/")
credential_db = COUCH_SERVER['tweeter_credentials']

TAGS = ['auspol','ausvotes','AusVotes19','ausvote2019' ,'auspol2019', 'ausvotes2019', 'ausvotes19']

MASTER_RANK = 0

try:
	tweet_db = COUCH_SERVER.create('tweeter_test')
except:
	tweet_db = COUCH_SERVER['tweeter_test']

try:
	users_db = COUCH_SERVER.create('users_twitter')
except:
	users_db = COUCH_SERVER['users_twitter']

databases = [tweet_db, users_db]


def app(harvester_type, twitter_credential, comm):
	harvester = None
	if harvester_type == 'api_stream':
		harvester = StreamTweetHarvester(twitter_credential, get_tracking_keywords(), comm)
	elif harvester_type == 'api_search':
		harvester = KeywordsHarvester(twitter_credential, get_tracking_keywords(), comm)
	else:
		harvester = StreamTweetHarvester(twitter_credential, get_tracking_keywords(), comm)
	print(datetime.datetime.now(), "tweeter user in use ", twitter_credential.id, harvester.comm.Get_rank())

	harvester.start_harvesting()


def get_boundary():
	return [110.0,-44.0,159.0,-8.0]


def get_tracking_keywords():
	df = pd.read_csv('csv_files/political_party_attributes.csv', encoding = "ISO-8859-1")
	temp = TAGS

	# Add party twitter page
	for text in df[df.twitter.notnull()].twitter.values:
		temp.extend(['@' + x.strip() for x in text.split(',')])

	# Add party name
	for text in df[df.party_name.notnull()].party_name.values:
		temp.extend([x.lower().strip() for x in text.split(',')])

	# Add party abbr name
	for text in df[df.abbr.notnull()].abbr.values:
		temp.extend([x.lower().strip() for x in text.split(',')])

	# Add leader name
	for text in df[df.leader.notnull()].leader.values:
		temp.extend([x.lower().strip() for x in text.split(',')])

	# Add leader twitter
	for value in df[df.leader_twitter.notnull()].leader_twitter.values:
		temp.extend(['@' + x.strip() for x in value.split(',')])

	return temp


def get_twitter_credentials():
	user = None
	for index, id in enumerate(credential_db):
		doc = credential_db[id]
		if doc['in_use'] == "0":
			user = doc
			doc['in_use'] = "1"
			try:
				credential_db.save(doc)
				break
			except:
				print(datetime.datetime.now(), "Couldn't lock user")
				exit(0)
	if not user:
		print(datetime.datetime.now(), " Couldn't lock any user ")
		exit(0)

	return user


def main(argv):
	comm = MPI.COMM_WORLD
	rank = comm.Get_rank()
	if rank == MASTER_RANK:
		user = get_twitter_credentials()
		atexit.register(exit_handler, user)
		try:
			harvester_type = 'api_streamline'
			if len(argv) > 1:
				harvester_type = argv[1]
				app(harvester_type, user, comm)
			else:
				app(harvester_type, user, comm)
		finally:
			exit_handler(user)

	elif rank == 1:
		db_saver = Saving_Layer(get_boundary(), databases, comm)
		while True:
			data = comm.recv(source=MASTER_RANK, tag=1)
			db_saver.save_tweet_to_db(data)

def exit_handler(user):
	print(datetime.datetime.now(), " : ", 'Application is ending!')
	if user:
		doc = credential_db[user['_id']]
		if doc['in_use'] == "1":
			user = doc
			doc['in_use'] = "0"
			credential_db.save(doc)
			print(datetime.datetime.now(), " : ", user['_id'], " is unlocked")


if __name__ == "__main__":
	main(sys.argv)


