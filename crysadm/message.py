__author__ = 'powergx'
from flask import request, Response, render_template, session, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
from datetime import datetime, timedelta
import util
import json
import uuid


@app.route('/messagebox')
@requires_auth
def messagebox():
    user = session.get('user_info')
    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None
    info_msg = None
    if session.get('info_message') is not None:
        info_msg = session.get('info_message')
        session['info_message'] = None

    msgs_key = 'user_messages:%s' % user.get('username')

    msg_box = list()
    show_read_all = False
    for b_msg_id in r_session.lrange(msgs_key, 0, -1):
        msg_key = 'user_message:%s' % b_msg_id.decode('utf-8')
        b_msg = r_session.get(msg_key)
        if b_msg is None:
            r_session.lrem(msgs_key, msg_key)
            continue

        msg = json.loads(b_msg.decode('utf-8'))
        if show_read_all or not msg.get('is_read'):
            show_read_all = True
        msg_box.append(msg)

    return render_template('messages.html', err_msg=err_msg, info_msg=info_msg, messages=msg_box, show_read_all=show_read_all)

@app.route('/message_detail/<message_id>')
@requires_auth
def message_detail(message_id):
    msg_key = 'user_message:%s' % message_id
    b_msg = r_session.get(msg_key)
    if b_msg is None:
        session['error_message']='邮件已被删除'
        return redirect(url_for('messagebox'))
    msg=json.loads(b_msg.decode('utf-8'))
    if msg.get('is_read') == False:
       msg['is_read'] = True
       r_session.set(msg_key, json.dumps(msg))
    return render_template('user_message.html',msg=msg)

@app.route('/message/action', methods=['POST'])
@requires_auth
def message_action():
    user = session.get('user_info')

    if request.form['btn'] is None:
        util.set_message('参数错误')
        return redirect(url_for('messagebox'))

    msgs_key = 'user_messages:%s' % user.get('username')

    all_message = r_session.lrange(msgs_key, 0, -1)

    for val in request.form:
        if len(val) < 4 or val[0:3] != 'msg':
            continue

        msg_id = val[4:]
        if bytes(msg_id, 'utf-8') not in all_message:
            continue

        if request.form['btn'] == 'mark_as_read':
            msg_key = 'user_message:%s' % msg_id

            msg = json.loads(r_session.get(msg_key).decode('utf-8'))
            msg['is_read'] = True
            r_session.set(msg_key, json.dumps(msg))

        elif request.form['btn'] == 'delete':
            r_session.lrem(msgs_key, msg_id)
            msg_key = 'user_message:%s' % msg_id
            r_session.delete(msg_key)

    return redirect(url_for('messagebox'))

@app.route('/message/reply', methods=['POST'])
@requires_auth
def message_reply():
    user = session.get('user_info')
    message_id = request.values.get('origin_mail')
    content = request.values.get('content')
    summary = request.values.get('summary')
    if summary == '':
        session['error_message'] = '简述必需填写'
        return redirect(url_for('messagebox'))
    content = '{:<30}'.format(summary) + content
    msg_key = 'user_message:%s' % message_id
    b_msg = r_session.get(msg_key)
    if b_msg is None:
        session['error_message']='邮件不存在，无法回复'
        return redirect(url_for('messagebox'))
    msg=json.loads(b_msg.decode('utf-8'))
    if 'sender' not in msg.keys():
        session['error_message']='发信人未知，无法投递'
        return redirect(url_for('messagebox'))
    session['info_message']=send_msg(msg['sender'],msg['subject'],content,3600 * 24 * 31,user.get('username'))
    return redirect(url_for('messagebox'))

@app.route('/delall_msg')
@requires_admin
def del_all_msg():
    for k in r_session.keys('user_messages:*'):
        r_session.delete(k.decode('utf-8'))
    return '删除成功'


def send_msg(username, subject, content, expire=3600 * 24 * 31, sender='Admin'):
    if bytes(username, 'utf-8') not in r_session.smembers('users'):
        return '找不到该用户。'
    msgs_key = 'user_messages:%s' % username
    msg_id = str(uuid.uuid1())
    msg = dict(id=msg_id, subject=subject, content=content,sender=sender,
               is_read=False, time=datetime.now().strftime('%Y-%m-%d %H:%M'))
    msg_key = 'user_message:%s' % msg_id
    r_session.setex(msg_key, json.dumps(msg), expire)
    r_session.lpush(msgs_key, msg_id)
    return '发送成功'
