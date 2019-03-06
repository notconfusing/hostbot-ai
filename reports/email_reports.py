import json
import os, sys
import datetime

from hostbotai.utils import load_con_from_config, load_session_from_con


BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
sys.path.append(BASE_DIR)

db_session = load_session_from_con(load_con_from_config('internalbot.my.cnf'))

### FILTER OUT DEPRECATION WARNINGS ASSOCIATED WITH DECORATORS
# https://github.com/ipython/ipython/issues/9242
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning, message='.*use @default decorator instead.*')

#####################################################


TOTAL_LABEL = "total count"
DATE_FORMAT_SEC = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_DAY = "%Y-%m-%d"


def date_to_str(date, by_day=True):
    date_format = DATE_FORMAT_DAY if by_day else DATE_FORMAT_SEC
    return date.strftime(date_format)


def str_to_date(date_str, by_day=True):
    date_format = DATE_FORMAT_DAY if by_day else DATE_FORMAT_SEC
    return datetime.datetime.strptime(date_str, date_format)


def run_query_for_days(query_str, today, days=7):
    today_str = date_to_str(today, by_day=False)
    last_week = today - datetime.timedelta(days=days)
    last_week_str = date_to_str(last_week, by_day=False)
    result = db_session.execute(query_str, {"from_date": last_week_str, "to_date": today_str}).fetchall()
    return result


def transform_result_to_dict(result):
    type_to_date_to_val = {}
    for row in result:
        (this_type, year, month, day, count) = row
        date = str_to_date("{0}-{1}-{2}".format(year, month, day))

        if this_type not in type_to_date_to_val:
            type_to_date_to_val[this_type] = {}
        type_to_date_to_val[this_type][date] = count
    return type_to_date_to_val


def generate_html_table(result, today, title):
    d = transform_result_to_dict(result)
    return generate_html_table_from_dict(d, today, title)


def generate_html_table_from_dict(type_to_date_to_val, today, title):
    days_str = [date_to_str(today - datetime.timedelta(days=i)) for i in range(0, 7)]
    days = [str_to_date(d) for d in days_str]  # to make everything 00:00:00
    past_days = days[1:]
    html = """
        <tr>
            <th>{7}</th>
            <th>{0} (Today)</th> 
            <th>Past Mean</th>
            <th>{1}</th>
            <th>{2}</th>
            <th>{3}</th>
            <th>{4}</th>
            <th>{5}</th>
            <th>{6}</th>
        </tr>""".format(*days_str, title)

    for type in sorted(type_to_date_to_val.keys()):
        this_data = type_to_date_to_val[type]
        past_mean = round(sum([this_data[d] if d in this_data else 0 for d in past_days]) / len(past_days) if len(
            past_days) > 0 else 0, 2)

        html += """
            <tr>
                <td>{0}</td>
                <td class='highlight'>{1}</td> 
                <td class='highlight'>{2}</td>
                <td>{3}</td>
                <td>{4}</td>
                <td>{5}</td>
                <td>{6}</td>
                <td>{7}</td>
                <td>{8}</td>                
            </tr>""".format(type,
                            (this_data[days[0]] if days[0] in this_data else 0),
                            past_mean,
                            *[this_data[d] if d in this_data else 0 for d in past_days])

    return html


def send_report(subject, html):
    with open(os.path.join(BASE_DIR, "config", "default_config.json"), "r") as f:
        email_config = json.load(f)
    save_report_locally(subject, html)
    try:
        send_email(email_config["fromaddr"], email_config["toaddrs"], subject, html)
    except ConnectionRefusedError:
        print('It looks like you cant SMTP from this machine')


def save_report_locally(subject, html):
    with open(os.path.join(BASE_DIR, 'logs', subject), 'w') as outf:
        outf.write(html)


def send_email(fromaddr, toaddrs, subject, html):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    COMMASPACE = ', '

    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = COMMASPACE.join(toaddrs)
    msg['Subject'] = subject

    body = html
    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP('localhost', 25)
    text = msg.as_string()
    server.sendmail(fromaddr, toaddrs, text)
    server.quit()
    print("Sent email from {0} to {1} recipients".format(fromaddr, len(toaddrs)))


######################################################################
######### HOSTBOT 		  ############################################
######################################################################


def generate_candidate_stats(today=datetime.datetime.utcnow(), days=7, html=True, label="Hostbot"):
    query_str = """select
                coalesce(invite_sent,'no-decision-yet'), YEAR(created_at), MONTH(created_at), DAY(created_at),count(invite_sent) 
                from (select * from candidates where :to_date <= created_at <= :from_date) day_cands
                group by YEAR(created_at), MONTH(created_at), DAY(created_at), coalesce(invite_sent,'no-decision-yet');"""
    result = run_query_for_days(query_str, today, days=days)
    if not html:
        return result
    return generate_html_table(result,
                               str_to_date(date_to_str(today)),
                               label)  # to make everything 00:00:00





######################################################################
######### GENERATE REPORT  ###########################################
######################################################################


css = """
<style>
table {
    border-collapse: collapse;
    width: 100%;
}
th {
    background-color:#dddddd
}
th, td {
    padding: 8px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}
tr:hover{
    background-color:#f5f5f5
}
td.highlight {
    background-color:#eeeeee
}
</style>
"""


def generate_report(today=datetime.datetime.utcnow(), days=7):
    html = "<html><head>" + css + "</head><body>"
    html += "<h2>Number of records stored per day</h2>"
    # html += "<h3>Reddit:</h3>"
    html += "<table>"
    html += "<h3>Hostbot Candidate Stats</h3>"
    html += generate_candidate_stats(today, days)
    html += "</table>"
    html += "</body></html>"
    return html


#############################################################
#############################################################


if __name__ == "__main__":
    now = datetime.datetime.utcnow()
    end = datetime.datetime.combine(now, datetime.time())
    today = end - datetime.timedelta(seconds=1)
    html = generate_report(today, days=7)
    subject = "HostBot Database Report: {0}".format(date_to_str(today))
    send_report(subject, html)
