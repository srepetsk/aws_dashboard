from flask import Flask, flash, abort, redirect, url_for, request, render_template, make_response, json, Response, session
import os, sys
import config
import boto.ec2.elb
import boto
from datetime import datetime, timedelta
import time
from boto.ec2 import *

app = Flask(__name__)
app.config['SECRET_KEY'] = config.get_secret_key()

@app.route('/')
def index():

	list = []
	creds = config.get_ec2_conf()

	for region in config.region_list():
		conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
		zones = conn.get_all_zones()	
		instances = conn.get_all_instance_status(max_results=2000)
		instance_count = len(instances)
		ebs = conn.get_all_volumes()
		ebscount = len(ebs)
		unattached_ebs = 0
		unattached_eli = 0
		event_count = 0
	
		for instance in instances:
			events = instance.events
			if events:
				event_count = event_count + 1	

		for vol in ebs:
			state = vol.attachment_state()
			if state == None:
				unattached_ebs = unattached_ebs + 1

		elis = conn.get_all_addresses()
		eli_count = len(elis)


		for eli in elis:
			instance_id = eli.instance_id
			if not instance_id:
				unattached_eli = unattached_eli + 1

		connelb = boto.ec2.elb.connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
		elb = connelb.get_all_load_balancers()
		elb_count = len(elb)
		list.append({ 'region' : region, 'zones': zones, 'instance_count' : instance_count, 'ebscount' : ebscount, 'unattached_ebs' : unattached_ebs, 'eli_count' : eli_count, 'unattached_eli' : unattached_eli, 'elb_count' : elb_count, 'event_count' : event_count})
		
	return render_template('index.html',list=list)

# Show all unassociated EBS volumes for a particular region
@app.route('/ebs_volumes/<region>/')
def ebs_volumes(region=None):
	creds = config.get_ec2_conf()
	conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
	ebs = conn.get_all_volumes()
	ebs_vol = []	
	for vol in ebs:
		state = vol.attachment_state()
		ebs_info = { 'id' : vol.id, 'size' : vol.size, 'iops' : vol.iops, 'status' : vol.status }
		ebs_vol.append(ebs_info)
	return render_template('ebs_volume.html',ebs_vol=ebs_vol,region=region)
			
@app.route('/ebs_volumes/<region>/delete/<vol_id>')
def delete_ebs_vol(region=None,vol_id=None):
	creds = config.get_ec2_conf()	
	conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
	vol_id = vol_id.encode('ascii')
	vol_ids = conn.get_all_volumes(volume_ids=vol_id)
	for vol in vol_ids:
		vol.delete()
	return redirect(url_for('ebs_volumes', region=region))
	
@app.route('/elastic_ips/<region>/')
def elastic_ips(region=None):
	creds = config.get_ec2_conf()
	conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
	elis = conn.get_all_addresses()
	un_eli = []
	for eli in elis:
		instance_id = eli.instance_id
		if not instance_id:
			eli_info = { 'public_ip' : eli.public_ip, 'domain' : eli.domain}
			un_eli.append(eli_info)
	return render_template('elastic_ip.html',un_eli=un_eli,region=region)

@app.route('/elastic_ips/<region>/delete/<ip>')
def delete_elastic_ip(region=None,ip=None):
	creds = config.get_ec2_conf()
	conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
	ip = ip.encode('ascii')
	elis = conn.get_all_addresses(addresses=ip)

	for eli in elis:
		eli.release()
	return redirect(url_for('elastic_ips', region=region))
	
# Display list of all instances in the selected region
@app.route('/instance_events/<region>/')
def instance_events(region=None):
	creds = config.get_ec2_conf()
	conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
	instances = conn.get_only_instances()
	instance_list = []
	for instance in instances:
		instance_info = { 'instance_id' : instance.id, 'instance_type' : instance.instance_type, 'state' : instance.state, 'instance_launch' : instance.launch_time, 'instance_name' : instance.tags['Name'], 'instance_region' : region}
		# If the instance has a Point of Contact tag, add it now
		if 'POC' in instance.tags :
			instance_info.update({ 'instance_poc' : instance.tags['POC'] })
		# If the instance has a team tag, add it now
		if 'Team' in instance.tags :
			instance_info.update({ 'instance_team' : instance.tags['Team'] })
		# If the instance has a Usefor tag (i.e. dev, production, etc.) add it now
		if 'Usefor' in instance.tags :
			instance_info.update({ 'instance_use' : instance.tags['Use']})
		# If the instance has a shutdown time flag (time after which to shut the instance down), add it now
		if 'Shutoff Time' in instance.tags :
			aws_shutdown = int(instance.tags['Shutoff Time'])
			shutoff_readable = datetime.fromtimestamp(aws_shutdown/1000.0)
			instance_info.update({ 'instance_shutdown' : shutoff_readable})
			
		instance_list.append(instance_info)


	return render_template('instance_events.html', instance_list=instance_list)

# Get info back regarding VM boot extension and process it
@app.route('/instanceupdate', methods=['GET', 'POST'])
def instanceupdate(region=None):
	if request.method == 'POST':	
		# Set variables passed in from the session: instance ID, and extension (hours)
		region = request.form['region']
		form_id = request.form['instance_id']
		extension_hr = int(request.form['extension'])
		# Convert 
		millisecond_hr = int(3600000 * extension_hr)

		creds = config.get_ec2_conf()
		conn = connect_to_region(region, aws_access_key_id=creds['AWS_ACCESS_KEY_ID'], aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])

		# Get info about the instance; only the instance we want
		instance = conn.get_only_instances(filters={'instance-id': form_id})
		for i in instance:
			"Extending runtime of instance " + i.id + " by " + str(extension_hr) + " hours."
			
			# Set new shutoff time
			#new_shutoff_time = datetime.now() + timedelta(hours=hours)
			current_milli_time = lambda: int(round(time.time() * 1000))
			new_shutoff_time = current_milli_time() + millisecond_hr
			print "New instance shutoff time for " + i.tags['Name'] + " is " + str(datetime.fromtimestamp(new_shutoff_time/1000.0))

			# Determine new shutoff time
			# lt_datetime = datetime.datetime.strptime(i.launch_time, '%Y-%m-%dT%H:%M:%S.000Z')
			# lt_delta = datetime.datetime.utcnow() - lt_datetime
			# uptime = str(lt_delta)
			i.add_tag('Shutoff Time', new_shutoff_time)
	
		return redirect(url_for('index'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
	# <link rel="shortcut icon" href="{{ url_for('static', filename='favicon.ico') }}">
			
if __name__ == '__main__':
	app.debug = True
	app.run(host='0.0.0.0')
