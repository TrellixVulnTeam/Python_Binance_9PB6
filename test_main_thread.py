from datetime import datetime
import getopt
import sys
import sys
import os
import threading
import logging

from connector.binance_api import GetHistoricalData
from binance.client import Client

import pandas as pd
from pandas.io import sql

from modul_db import connect_db_engine, getPairsPrice, ActPriceInTable
from modul_TradingView import GetTAfromTV



def thread_function(name, engine, client, df_pairs, tmpName):
    logging.info("Thread %s: starting", name)

    getPairsDataFromExchange(engine, client, df_pairs, tmpName)

    logging.info("Thread %s: finishing", name)

def thread_functiontest(name, engine, client, df_pairs, tmpName):
    logging.info("Thread %s: starting", name)

    getPairsDataFromExchange(engine, client, df_pairs, tmpName)

    logging.info("Thread %s: finishing", name)

class myThread (threading.Thread):
    def __init__(self, threadID, name, engine, client, df_pairs):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = engine
        self.client = client
        self.df_pairs = df_pairs

    def run(self):
        print ("Starting " + self.name)

        getPairsDataFromExchange(engine, client, df_pairs, "th")

        print ("Exiting " + self.name)


# Pairs DB.binance_pairs nach Rangliste in DB.binance_gd200 sortieren
def setPairsPrioritaet(dfpairs, dfpairs200):

    dfpairs.loc[:, 'Prioritaet'] = 9999

    # Dataframe durchlaufen um  Daten abzurufen
    for index, row in df_pairs200.iterrows():
        pair = row["pairs"]
        RecPos = index

        # Spalte close mit lowma vergleichen, Ergebnis = True = 1 setzen
        dfpairs.loc[
            (
                (dfpairs['pairs'] == pair)
            ),
            'Prioritaet'] = RecPos + 1

    dfpairs.sort_values('Prioritaet', inplace=True)

    return dfpairs


def getPairsDataFromExchange(engine, client, df_pairs, tmp_table):

    # Dataframe durchlaufen um die Daten abzurufen ------------------------------------------------------------
    forcnt = 1
    listNull = []

    for index, row in df_pairs.iterrows():
        pair = row["pairs"]

        # df = GetSelectedData(client, row["pairs"], interval, howLong)
        df = GetHistoricalData(client, row["pairs"], interval, dayAgo, "")

        # wenn kein price geholt, dann pair in Liste speichern und for Schleife
        # auf den naechsten Wert springen
        if type(df) is bool:
            # rs = engine.execute("UPDATE binance_pairs SET Prioritaet=2 WHERE pairs='" +
            #                         row["pairs"] + "'")

            print(
                row["pairs"] + " keine Datensaetze !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # pair ohne Daten in Liste speichern
            listNull.append(row["pairs"])
            continue

        # Zusatz-Info in df einfügen: pair,interval
        df.insert(0, "pairs", row["pairs"])
        df.insert(1, "interval", intervalDB)

        # Daten temporaer in binance_price_temp speichern
        engine.execute("DROP TABLE IF EXISTS " + "binance_price_temp_" + tmp_table)
        tmpStr = "binance_price_temp_" + tmp_table
        print(tmpStr)
        df.to_sql(tmpStr, engine, if_exists='replace')

        # Daten von binance_price_temp nach binance_price verschieben
        # rs = engine.execute('INSERT IGNORE INTO binance_price SELECT * FROM binance_price_temp')
        strsql = """
                INSERT INTO binance_price(`TimeCET`, `pairs`, `interval`, `open`, `high`, `low`, `close`, `volume`)
                SELECT * FROM binance_price_temp_""" + tmp_table + """ t
                ON DUPLICATE KEY UPDATE `open`=t.`open`, `high`=t.`high`, `low`=t.low, `close`=t.close, `volume`=t.volume
                        """
        # print(strsql)
        rs = engine.execute(strsql)

        # Technische Analyse von TradingView holen und in DB.binance_pairs speichern
        pairTA = GetTAfromTV(pair)
        sqlstr = "UPDATE `binance_pairs` SET `TechnAnalyse`='" + \
            pairTA + "' WHERE pairs = '" + pair + "'"
        sql.execute(sqlstr, engine)

        # Update des aktuellen pair_price min den Auswertungstabellen
        # binance_gd200, binance_rsima, binance_gd50vross200

        # Sind Datensaetze vorhanden
        idflen = len(df)
        if(idflen > 0) or not df.empty:
            ActPriceInTable(engine, df, pair)

        # pair in DB.binance_price_down speichern fuer Auswertung m_evaluation_price
        rs = engine.execute(
            "INSERT INTO binance_price_down(pairs, TechnAnalyse) Values('" + pair + "', '" + pairTA + "')")

        print(str(forcnt) + " von " + str(df_len) + " " +
              row["pairs"] + " = " + str(len(df)) + " Datensaetze")
        forcnt += 1

    return listNull


def main(argv):

    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv, "hi:o:", ["ifile=", "ofile="])
    except getopt.GetoptError:
        print('test.py -i <inputfile> -o <outputfile>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('test.py -i <inputfile> -o <outputfile>')
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg

    print('Input file is "', inputfile)
    print('Output file is "', outputfile)


# ----------------------------------------------------------------------------------------------------------------------
# Execute the following code only when executing main.py (not when importing it)
if __name__ == '__main__':
    # Argumente bei Programmstart auswerten

    # main(sys.argv[1:])

    print('Number of arguments:', len(sys.argv), 'arguments.')
    print('Argument List:', str(sys.argv))

    """
    args = sys.argv
    if len(sys.argv) > 1:
        
        print(args[1])
        if int(args[1]) in range(1,100):
            paraHours = args[1]
            print(paraHours)
            
    else:
        # Verbindung mit Datenbank aufbauen
        engine = connect_db_engine()

        df_max = pd.read_sql("SELECT MAX(TimeCET) FROM binance_price", engine)

        # Datenbankverbindung loesen
        engine.dispose()

        sys.exit()
        
    """

    paraHours = 10

    while True:

        # Verbindung mit Datenbank aufbauen
        engine = connect_db_engine()

        # Startzeit der Verarbeitung in Variable speichern
        dBeginDown = datetime.now()

        # Verbindung mit Binance-API herstellen
        api_key = "YRh7OHf8IUjumPzc27pVsE4VJKdR8kT7a9oRxDtREpMsivQ6wZ6XwXH3eVcFDHpc"
        api_secret = "9CCnqUKby6t6PDbIYj7vBBXg7WNXsUIXnrxpA3vIttKfXGuVmiLpTsqsFZu1fdkH"
        client = Client(api_key, api_secret)

        # Setup der Variablen
        howLong = 1
        dayAgo = str(paraHours) + " hours ago UTC"
        print(dayAgo)

        #symbol = "SOLUSDT"

        interval = Client.KLINE_INTERVAL_5MINUTE
        intervalDB = 5

        # Abruf der cryptos aus DB
        df_pairs = pd.read_sql(
            'SELECT * FROM binance_pairs WHERE Prioritaet > 0', engine)
        df_len = len(df_pairs)
        print("full " + str(df_len))

        # Daten speichern in csv
        # df_pairs.to_csv("./csv/pairs_full.csv", decimal=";")


        # Abruf der cryptos aus DB GD200
        df_pairs200 = pd.read_sql(
            'SELECT pairs FROM `binance_gd200` ORDER BY `startDate` DESC', engine)

        # pairs aus DB.binance_pairs holen und nach Prioritaet fuer den Downloads setzen
        df_pairs = setPairsPrioritaet(df_pairs, df_pairs200)

        # Daten speichern in csv
        # df_pairs.to_csv("./csv/pairs_gdsort.csv", decimal=",")

        # Pairs splitten nach GD200 und Rest
        df_pairs200 = df_pairs.iloc[:50]
        print("full " + str(len(df_pairs200)))

        # Daten speichern in csv
        # df_pairs200.to_csv("./csv/pairs_gd200.csv", decimal=",")

        df_pairs = df_pairs.iloc[50:]
        print("full " + str(len(df_pairs)))

        # Daten speichern in csv
        # df_pairs.to_csv("./csv/pairs_gdrest.csv", decimal=",")

        # sys.exit()

        # Create new threads für Download der ersten 00 pairs
        # thread1 = myThread(1, "Thread-GD200", engine, client, df_pairs200)
        
        # Start new Threads
        # thread1.start()

        # Verbindung mit Datenbank aufbauen
        engine200 = connect_db_engine()
        x1 = threading.Thread(target=thread_function, args=(1, engine200, client, df_pairs200, "th",))

        logging.info("Main    : before running thread")

        x1.start()
        logging.info("Main    : wait for the thread to finish")
        # x1.join()
        logging.info("Main    : all done")

        # Durchlauf df, Daten von Exchange holen
        # Verbindung mit Datenbank aufbauen
        enginerest = connect_db_engine()
        x2 = threading.Thread(target=thread_functiontest, args=(2, enginerest, client, df_pairs, "rest",))

        logging.info("Main    : before running thread")
        x2.start()
        logging.info("Main    : wait for the thread to finish")
        # x.join()
        logging.info("Main    : all done")

        # listNull = getPairsDataFromExchange(engine, client, df_pairs, "rest")
        # logging.info("Main    : wait for the thread to finish")
        # x.join()

        # Abschlussarbeiten nach Download ------------------------------------------------

        x2.join

        listNull = []



        # pairs ohne price aus download in DB-Tabelle und CSV speichern
        print("pairs ohne price aus download in DB-Tabelle und CSV speichern")
        df_Null = pd.DataFrame(listNull, columns=["pair_noPrice"])
        if len(df_Null) > 0:
            df_Null.to_sql("binance_pairsNoPrice", engine, if_exists='replace')

            # pairs ohne price in CSV speichern
            f = open("pairsNull.txt", "w")
            for pairNull in listNull:
                f.writelines(pairNull)
            f.close()
        else:
            rs = engine.execute("DROP TABLE IF EXISTS binance_pairsNoPrice")

            if os.path.exists("pairsNull.txt"):
                os.remove("pairsNull.txt")

        # Datenbankverbindung loesen
        #engine.dispose()
        #engine200.dispose()
        #enginerest.dispose()

        # Loop Zeit nach indivueller Eingabe auf 1Std zurücksetzen
        paraHours = 1
        print("naechster Durchlauf mit 1 Std")

        print("Beginn Download Price " + str(dBeginDown))
        print("Ende Download Price " + str(datetime.now()))
