#!/usr/bin/python3
from multiprocessing import Lock
from queue import Queue
from dotenv import load_dotenv
import os
from pathlib import Path
import threading
import logging
import datetime
from netmiko import ConnectHandler
import json
from logicMonitor import logicmonitor_get
import sys

sys.tracebacklimit = 0
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)
ssh_user = os.environ['USER']
ssh_pwd = os.environ['PWD']

num_threads = 10  # number of simultaneous threads
enclosure_queue = Queue()
print_lock = threading.Lock()

built_year = {}
built_year['01'] = '1997'
built_year['02'] = '1998'
built_year['03'] = '1999'
built_year['04'] = '2000'
built_year['05'] = '2001'
built_year['06'] = '2002'
built_year['07'] = '2003'
built_year['08'] = '2004'
built_year['09'] = '2005'
built_year['10'] = '2006'
built_year['11'] = '2007'
built_year['12'] = '2008'
built_year['13'] = '2009'
built_year['14'] = '2010'
built_year['15'] = '2011'
built_year['16'] = '2012'
built_year['17'] = '2013'
built_year['18'] = '2014'
built_year['19'] = '2015'
built_year['20'] = '2016'
built_year['21'] = '2017'
built_year['22'] = '2018'
built_year['23'] = '2019'
built_year['24'] = '2020'
built_year['25'] = '2021'
built_year['26'] = '2022'
built_year['27'] = '2023'
built_year['28'] = '2024'
built_year['29'] = '2025'
built_year['30'] = '2026'


def deviceconnector(i, q, l):
    while True:
        host = q.get()
        l.acquire()
        try:
            print(host + " {}: Executing".format(i))
            logging.info(host + ' : Executing')
        finally:
            l.release()

        ap_inventory = wlcconnector(host)
        for ap in ap_inventory[host]['aps']:
            yy = ap['serial'][3:5]
            ww = ap['serial'][5:7]
            ap['Year'] = built_year[yy]
            ap['Week'] = ww
            ap['Expire'] = int(built_year[yy]) + 10
            if int(built_year[yy]) + 10 <= datetime.date.today().year:
                if ap_inventory[host]['mic_config'] == "Not enabled.":
                    ap['alarm'] = True
                else:
                    ap['alarm'] = False
            else:
                ap['alarm'] = False

        site = {'AP': ap_inventory}
        with open(host + '.json', 'w') as out:
            json.dump(site, out, indent=4)
        logging.info(host + ': Done! JSON created')
        q.task_done()


def wlcconnector(host):
    ap_inventory = {host: {'aps': [], 'mic_config': ''}}
    try:
        with ConnectHandler(ip=host,
                            port=22,
                            username=ssh_user,
                            password=ssh_pwd,
                            device_type='cisco_wlc_ssh') as ch:

            ap_summary = ch.send_command_timing("sh ap summary")
            ap_summary = ap_summary.split("\n", 9)[9]
            ap_summary = ap_summary.split("\n")
            ap_summary = [i.split(' ')[0] for i in ap_summary]
            ap_names = []
            for i in ap_summary:
                ap_names.append(i)

            mic_config = ch.send_command_timing(
                'grep include \"ap cert-expiry-ignore mic enable\" \"show run-config commands\"')
            if "Press any key to continue" in mic_config:
                mic_config = ch.send_command_timing("y")
            mic_config = mic_config.split("\n")
            if mic_config[0] == "":
                ap_inventory[host]['mic_config'] = "Not enabled."
            else:
                ap_inventory[host]['mic_config'] = mic_config[0]

            for ap in ap_names:
                ap_name = ap
                ap_sn = ch.send_command_timing("sh ap inventory " + ap)
                ap_sn = ap_sn.split("\n")
                ap_sn = [i.split(',') for i in ap_sn]
                for ap2 in ap_sn:
                    for sn in ap2:
                        if "SN:" in sn:
                            sn = sn.strip()
                            sn = sn.split(':')
                            ap_inventory[host]['aps'].append({
                                'name': ap_name,
                                'serial': sn[1].strip()
                            })
            ch.disconnect()
    except:
        logging.error(host + ": Problem Connecting")
        ap_inventory = "NA"
    return ap_inventory


def main():
    lock = Lock()
    logname = datetime.datetime.now()
    logname = logname.strftime("%d%b%y" + "-" "%H" + "." + "%M")
    logging.basicConfig(filename=logname + '.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    for i in range(num_threads):
        thread = threading.Thread(target=deviceconnector, args=(i, enclosure_queue, lock,))
        thread.setDaemon(True)
        thread.start()
    resourcePath = '/device/devices'
    queryParams = '?fil-ter=customProperties.name:ctag.devicetype,customProperties.value:Wireless%20Controller&size=1000'
    try:
        hosts = logicmonitor_get(Company='xyz', resourcePath=resourcePath, queryParams=queryParams)
        logging.info('Connection to Logic Monitor successful')
    except:
        logging.error('unable to connect to Logic Monitor')
        exit()

    try:

        for host in hosts['data']['items']:  # Hosts should be a list that needs to be defined somewhere..
            enclosure_queue.put(host['name'])

        enclosure_queue.join()
    except:
        logging.error("Something with the API Broke!")
        logging.error(hosts['status'])
        exit()
    return  # Maintain this return


if __name__ == '__main__':
    log_name = datetime.datetime.now()
    log_name = log_name.strftime("%d%b%y" + "-" "%H" + "." + "%M")
    logging.basicConfig(filename=log_name + '.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s',
                        level=logging.WARNING)
    main()

''' 
01-05 = January
06-09 = February
10-14 = March
15-18 = April
19-22 = May
23-27 = June
28-31 = July
32-35 = August
36-40 = September
41-44 = October
45-48 = November
49-52 = December

Normally 2 possible responses from the grep:
['', 'There are 0 lines matching the pattern ap cert-expiry-ignore mic enable ', '', '(Cisco Controller) >']
[' ap cert-expiry-ignore mic enable', '', 'There are 1 lines matching the pattern ap cert-expiry-ignore mic enable ', '', '(US-CZM-10068-WLC-M-FLEX) >']

'''
