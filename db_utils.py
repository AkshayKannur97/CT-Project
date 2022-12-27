'''**************************************************************************
Author:         Akshay C P
Date:           06 Dec 2022
DEscription:    Script to manage sqlite3 database
**************************************************************************'''

import sqlite3


def fetch_calibration_for_channel(channel):
    conn = sqlite3.connect('./data.db')
    sql = f'''SELECT * FROM Calibration WHERE channel=?;'''
    print(sql)
    cur = conn.cursor()
    try:
        cur.execute(sql, (channel,))
    except sqlite3.OperationalError as e:
        print(e)
    else:
        row = cur.fetchone() or (channel, 0, 1, 100, 100, 0, 100)
        print(row)
        return row


def update_calibration_for_channel(channel, **kwargs):
    conn = sqlite3.connect('./data.db')
    cur = conn.cursor()
    sql = 'INSERT OR IGNORE INTO Calibration VALUES (?, 0, 1, 100, 100, 0, 100)'
    cur.execute(sql, (channel,))
    for col in kwargs.keys():
        sql = f'UPDATE Calibration SET "{col}" = ? WHERE channel = ?'
        try:
            cur.execute(sql, (kwargs[col], channel))
            print(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def update_test_paths(test_id, **kwargs):
    conn = sqlite3.connect('./data.db')
    cur = conn.cursor()
    for col in kwargs.keys():
        sql = f''' UPDATE Tests SET "{col}" = ? WHERE id = ? '''
        try:
            cur.execute(sql, (kwargs[col], test_id))
            print(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


if __name__ == '__main__':
    # update_calibration_for_channel('ch12', decimals=34, resolution=45)
    # fetch_calibration_for_channel('ch12')
    # fetch_calibration_for_channel('ch2')
    update_test_paths('003', pdf_path='/tmp/098475364.png')
