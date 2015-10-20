"""
<Program>
  views.py

<Started>
  October, 2008

<Author>
  Ivan Beschastnikh
  Jason Chen
  Justin Samuel
  Sai Kaushik Borra

<Purpose>
  This module defines the functions that correspond to each possible request
  made through the html frontend. The urls.py file in this same directory
  lists the url paths which can be requested and the corresponding function name
  in this file which will be invoked.
"""

import os
import sys
import shutil
import subprocess
import xmlrpclib
import re

# Needed to escape characters for the Android referrer...
import urllib

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.core.context_processors import csrf
from django.core.exceptions import PermissionDenied

# Used to display meaningful OpenID/OAuth error messages to the user
from django.contrib.messages.api import get_messages
from django.contrib import messages
from django.shortcuts import render_to_response, redirect
from social_auth.utils import setting
from django.template import RequestContext
# Any requests that change state on the server side (e.g. result in database
# modifications) need to be POST requests. This is for protecting against
# CSRF attacks (part, but not all, of that is our use of the CSRF middleware
# which only checks POST requests). Sometimes we use this decorator, sometimes
# we check the request type inside the view function.
from django.views.decorators.http import require_POST

# Make available all of our own standard exceptions.
from clearinghouse.common.exceptions import *

# This is the logging decorator use use.
from clearinghouse.common.util.decorators import log_function_call
from clearinghouse.common.util.decorators import log_function_call_without_return

# For user registration input validation
from clearinghouse.common.util import validations

from clearinghouse.common.util import log

from clearinghouse.website import settings
# FIXME: this patches the portability safe_type declaration, there might be a 
# cleaner way of doing this. We rely in the backup made by the safe module to
# reload type here.
import safe
__builtins__['type'] = safe._type

from clearinghouse.website import settings

# All of the work that needs to be done is passed through the controller interface.
from clearinghouse.website.control import interface

from clearinghouse.website.html import forms

from seattle.repyportability import *
add_dy_support(locals())

rsa = dy_import_module("rsa.r2py")

# For defining custom template tags
from django import template

# Importing models
from ..control.models import Sensor, SensorAttribute, Experiment, ExperimentSensor, ExperimentSensorAttribute, GeniUser

# Importing forms
from .forms import ExperimentForm, ExperimentSensorForm, ExperimentSensorAttributeForm


class LoggedInButFailedGetGeniUserError(Exception):
  """
  <Purpose>
  Indicates that a function tried to get a GeniUser record, and failed;
  while having passed the @login_required decorator. This means that a
  DjangoUser is logged in, but there is no corresponding GeniUser record.
  
  This exception should only be thrown from _validate_and_get_geniuser,
  and caught by methods with @login_required decorators.
  """





def _state_key_file_to_publickey_string(key_file_name):
  """
  Read a public key file from the the state keys directory and return it in
  a key string format.
  """
  fullpath = os.path.join(settings.SEATTLECLEARINGHOUSE_STATE_KEYS_DIR, key_file_name)
  return rsa.rsa_publickey_to_string(rsa.rsa_file_to_publickey(fullpath))





# The key used as the state key for new donations.
ACCEPTDONATIONS_STATE_PUBKEY = _state_key_file_to_publickey_string("acceptdonation.publickey")





def error(request):
  """
  <Purpose>
    If a OpenID/OAuth backend itself has an error(not a user or Seattle Clearinghouse's fault) 
    a user will get redirected here.  This can happen if the backend rejects the user or from
    user cancelation.

  <Arguments>
    request:
      An HTTP request object.

  <Exceptions>
    None

  <Side Effects>
    None

  <Returns>
    An HTTP response object that represents the error page.
  """
  #Retrieve information which caused an error 
  messages = get_messages(request)
  info =''
  try:
    user = _validate_and_get_geniuser(request)
    return profile(request, info, info, messages)
  except:
    return _show_login(request, 'accounts/login.html', {'messages' : messages}) 





@login_required
def associate_error(request):
  """
  <Purpose>
    If an error occured during the OpenId/OAuth association process a user will get
    redirected here.
  <Arguments>
    request:
      An HTTP request object.
    backend:
      An OpenID/OAuth backend ex google,facebook etc.
  <Exceptions>
    None
  <Side Effects>
    None
  <Returns>
    An HTTP response object that represents the associate_error page.
  """
  info=''
  error_msg = "Whoops, this account is already linked to another Seattle Clearninghouse user."
  return profile(request, info, error_msg)





def auto_register(request,backend=None,error_msgs=''):
  """
  <Purpose>
  Part of the SOCIAL_AUTH_PIPELINE whose order is mapped in settings.py.  If
  a user logs in with a OpenID/OAuth account and that account is not yet linked
  with a Clearinghouse account, he gets redirected here.
  If a valid username is entered then a new Seattle Clearinghouse user is created.

  <Arguments>
    request:
      An HTTP request object.
    backend:
      An OpenID/OAuth backend ex google,facebook etc.
  <Exceptions>

  <Side Effects>
    A new Seattle Clearinghouse user is created.
  <Returns>
    If a user passes in a valid username he continues the pipeline and moves
    forward in the auto register process.
  """
  # Check if a username is provided
  username_form = forms.AutoRegisterForm()
  if request.method == 'POST' and request.POST.get('username'):
    name = setting('SOCIAL_AUTH_PARTIAL_PIPELINE_KEY', 'partial_pipeline')
    username_form = forms.AutoRegisterForm(request.POST)
    if username_form.is_valid():
      username = username_form.cleaned_data['username']
      try:
        interface.get_user_without_password(username)
        error_msgs ='That username is already in use.'
      except DoesNotExistError:
        request.session['saved_username'] = request.POST['username']
        backend = request.session[name]['backend']
        return redirect('socialauth_complete', backend=backend)  
  name = setting('SOCIAL_AUTH_PARTIAL_PIPELINE_KEY', 'partial_pipeline')
  backend=request.session[name]['backend']
  return render_to_response('accounts/auto_register.html', {'backend' : backend, 'error_msgs' : error_msgs, 'username_form' : username_form}, RequestContext(request))





@log_function_call_without_return
@login_required
def profile(request, info="", error_msg="", messages=""):
  """
  <Purpose>
    Display information about the user account.
    This method requires the request to represent a valid logged
    in user. See the top-level comment about the @login_required()
    decorator to achieve this property.  User account is editable through this 
    method.
  <Arguments>
    request:
      An HTTP request object.  
    info:
      Additional message to display at the top of the page in a green box.
    error_msg:
      Additional message to display at top of the page in a red box.
    messages
      Django social auth error message
  <Exceptions>
    None
  <Side Effects>
    None
  <Returns>
    An HTTP response object that represents the profile page.
  """
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  email_form = forms.gen_edit_user_form(('email',),instance=user)
  affiliation_form = forms.gen_edit_user_form(('affiliation',),instance=user)
  password_form = forms.EditUserPasswordForm()
    
  if request.method == 'POST':
    if 'affiliation' in request.POST:
       affiliation_form = forms.gen_edit_user_form(('affiliation',), request.POST, instance=user)
       if affiliation_form.is_valid():
         new_affiliation = affiliation_form.cleaned_data['affiliation']
         interface.change_user_affiliation(user, new_affiliation)
         info ="Affiliation has been successfully changed to %s." % (user.affiliation)
    elif 'email' in request.POST:
       email_form = forms.gen_edit_user_form(('email',), request.POST, instance=user)
       if email_form.is_valid():
         new_email = email_form.cleaned_data['email']
         interface.change_user_email(user, new_email)
         info ="Email has been successfully changed to %s." % (user.email)
    elif 'password1' in request.POST:
       password_form = forms.EditUserPasswordForm(request.POST, instance=user)
       if password_form.is_valid():
         new_password = password_form.cleaned_data['password1']
         interface.change_user_password(user, new_password)
         info ="Password has been successfully changed"
  
  username = user.username
  affiliation = user.affiliation
  email = user.email
  port = user.usable_vessel_port
  has_privkey = user.user_privkey != None
  #currently not used, needed if editing user port is allowed
  #port_range = interface.get_useable_ports()
  #port_range_min = port_range[0]
  #port_range_max = port_range[-1]
  
  return render_to_response('control/profile.html',
                            {'email_form' : email_form,
                             'affiliation_form' : affiliation_form,
                             'password_form' : password_form,
                             'username' : username,
                             'affiliation' : affiliation,
                             'email' : email,
                             'port' : port,
                             'api_key' : user.api_key,
                             'has_privkey' : has_privkey,
                             #'port_range_min' : port_range_min,
                             #'port_range_max' : port_range_max,
                             'info' : info,
                             'error_msg' : error_msg,
                             'messages' : messages},
                            context_instance=RequestContext(request))


def register(request):
  try:
    # check to see if a user is already logged in. if so, redirect them to profile.
    user = interface.get_logged_in_user(request)
  except DoesNotExistError:
    pass
  else:
    return HttpResponseRedirect(reverse("profile"))

  page_top_errors = []
  if request.method == 'POST':

    #TODO: what if the form data isn't in the POST request? we need to check for this.
    form = forms.GeniUserCreationForm(request.POST, request.FILES)
    # Calling the form's is_valid() function causes all form "clean_..." methods to be checked.
    # If this succeeds, then the form input data is validated per field-specific cleaning checks. (see forms.py)
    # However, we still need to do some checks which aren't doable from inside the form class.
    if form.is_valid():
      username = form.cleaned_data['username']
      password = form.cleaned_data['password1']
      affiliation = form.cleaned_data['affiliation']
      email = form.cleaned_data['email']
      pubkey = form.cleaned_data['pubkey']

      try:
        validations.validate_username_and_password_different(username, password)
      except ValidationError, err:
        page_top_errors.append(str(err))

      # NOTE: gen_upload_choice turns out to be a *string* when retrieved, hence '2'
      if form.cleaned_data['gen_upload_choice'] == '2' and pubkey == None:
        page_top_errors.append("Please select a public key to upload.")

      # only proceed with registration if there are no validation errors
      if page_top_errors == []:
        try:
          # we should never error here, since we've already finished validation at this point.
          # but, just to be safe...
          user = interface.register_user(username, password, email, affiliation, pubkey)
        except ValidationError, err:
          page_top_errors.append(str(err))
        else:
          return _show_login(request, 'accounts/login.html',
                             {'msg' : "Username %s has been successfully registered." % (user.username)})
  else:
    form = forms.GeniUserCreationForm()
  return render_to_response('accounts/register.html',
          {'form' : form, 'page_top_errors' : page_top_errors},
          context_instance=RequestContext(request))
  




def _show_login(request, ltemplate, template_dict, form=None):
    """
    <Purpose>
        Show the GENI login form

    <Arguments>
        request:
            An HTTP request object to use to populate the form
            
        ltemplate:
           The login template name to use for the login form. Right now
           this can be one of 'accounts/simplelogin.html' and
           'accounts/login.html'. They provide different ways of visualizing
           the login page.

        template_dict:
           The dictionary of arguments to pass to the template

        form:
           Either None or the AuthenticationForm to use as a 'form' argument
           to ltemplate. If form is None, a fresh AuthenticationForm() will be
           created and used.

    <Exceptions>
        None.

    <Side Effects>
        None. 

    <Returns>
        An HTTP response object that represents the login page on
        success.
    """
    if form == None:
        # initial page load
        form = AuthenticationForm()
        # set test cookie, but only once -- remove it on login
        #if not request.session.test_cookie_worked():
        request.session.set_test_cookie()
    template_dict['form'] = form
    return render_to_response(ltemplate, template_dict, 
            context_instance=RequestContext(request))
  
  
  
  

def login(request):
  try:
    # check to see if a user is already logged in. if so, redirect them to profile.
    user = interface.get_logged_in_user(request)
  except DoesNotExistError:
    pass
  else:
    return HttpResponseRedirect(reverse("profile"))

  ltemplate = 'accounts/login.html'
  if request.method == 'POST':
    form = AuthenticationForm(request.POST)
    
    if not request.session.test_cookie_worked():
      request.session.set_test_cookie()
      return _show_login(request, ltemplate, {'err' : "Please enable your cookies and try again."}, form)

    if request.POST.has_key('jsenabled') and request.POST['jsenabled'] == 'false':
      return _show_login(request, ltemplate, {'err' : "Please enable javascript and try again."}, form)

    try:
      interface.login_user(request, request.POST['username'], request.POST['password'])
    except DoesNotExistError:
      return _show_login(request, ltemplate, {'err' : "Wrong username or password."}, form)
      
    # only clear out the cookie if we actually authenticate and login ok
    request.session.delete_test_cookie()
    
    return HttpResponseRedirect(reverse("profile"))
    
  # request type is GET, show a fresh login page
  return _show_login(request, ltemplate, {})





def logout(request):
  interface.logout_user(request)
  # TODO: We should redirect straight to login page
  return HttpResponseRedirect(reverse("profile"))





@login_required
def help(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  return render_to_response('control/help.html', {'username': user.username},
          context_instance=RequestContext(request))


def accounts_help(request):
  return render_to_response('accounts/help.html', {}, 
          context_instance=RequestContext(request))

def home(request):
  return render_to_response('accounts/home.html', {},
          context_instance=RequestContext(request))

def irbnuts(request):
  return render_to_response('accounts/IRBnuts.html', {},
          context_instance=RequestContext(request))

def rterms(request):
  return render_to_response('accounts/rterms.html', {},
          context_instance=RequestContext(request))

def doterms(request):
  return render_to_response('accounts/doterms.html', {},
          context_instance=RequestContext(request))

def dotechinfo(request):
  return render_to_response('accounts/dotechinfo.html', {},
          context_instance=RequestContext(request))

def about(request):
  return render_to_response('accounts/about.html', {},
          context_instance=RequestContext(request))

@login_required
def expsuccess(request):
    """
    A view which displays that an experiment has been submitted successfully
    """
    return render_to_response('control/expsuccess.html', {},
          context_instance=RequestContext(request))

@login_required
def experiments(request):
    """
    If an experiment id is provided:
        This displays all the data that belongs to the provided experiment id
    Else:
        This displays a list of all the experiments submitted by the logged in user
    """

    # Checking if a valid user id is found or not
    try:
        user = _validate_and_get_geniuser(request)
    except LoggedInButFailedGetGeniUserError:
        return _show_failed_get_geniuser_page(request)

    context_instance = RequestContext(request)
    exp_id = request.GET.get('id')

    # If the experiment id is NOT provided through GET
    # Display a list of experiments which are submitted by the logged in user
    if exp_id is None:
        experiments_list = Experiment.objects.filter(user=user.id).values().order_by('-date_created')
        context_dict = {'username': user.username, 'experiments': experiments_list}

    # If the experiment id is PROVIDED through GET
    else:
        # Collecting data of this experiment from Experiment model
        experiment = Experiment.objects.select_related('user').get(id=exp_id, user=user.id)

        # If the logged in user did NOT submit this experiment
        if not experiment:
            raise PermissionDenied

        # If the logged in user SUBMITTED this experiment
        else:
            # Collecting data of this experiment from Experiment Sensors model
            experiment_sensors = ExperimentSensor.objects.select_related('sensor').filter(experiment=exp_id)

            # Converting Frequency values which are by default seconds to sec(s)/min(s)/hour(s) accordingly
            for es in experiment_sensors:
                fr_val = es.frequency/60
                if fr_val >= 60:
                    es.frequency = str(fr_val/60)+' hour(s)'
                elif fr_val >= 1:
                    es.frequency = str(fr_val)+' min(s)'
                else:
                    es.frequency = str(es.frequency)+' sec(s)'

            # Collecting data of this experiment from Experiment Sensor Attributes model
            experiment_sensor_attribs = ExperimentSensorAttribute.objects.select_related('sensor_attribute__sensor').filter(experiment=exp_id)
            for esa in experiment_sensor_attribs:
                # Converting any PRECISION values to other forms, if necessary
                # The PRECISION value represent 'the number of decimal places' by default for all the sensors
                # For Location, the values correspond to a specific blur level of data such as:
                # 10 => State, 11 => Country, 01 or any other value correspond to the default value 'City'.
                if esa.sensor_attribute.precision_flag:
                    if esa.sensor_attribute.sensor.name == 'Location':
                        esa.precision_tag = ''                             # Used in template as a tag for 'Precision' heading
                        if esa.precision == 10:
                            esa.precision = 'State'
                        elif esa.precision == 11:
                            esa.precision = 'Country'
                        else:
                            esa.precision = 'City'
                    else:
                        esa.precision_tag = '(No.of Decimal Places)'        # Used in template as a tag for 'Precision' heading
                        if esa.precision == 0:
                            esa.precision = 'Full'
                else:
                     esa.precision = 'N/A'
            context_dict = {'username': user.username, 'exp': experiment, 'exp_sensors': experiment_sensors,
                        'exp_sensor_attribs': experiment_sensor_attribs}

    return render_to_response('control/experiments.html', context_dict, context_instance)


@login_required
def expreg(request):
    """
    <Purpose>
        Show the Experiment Registration Form
    <Returns>
        An HTTP response object that represents the experiment registration page on
        success.
    """
    # Obtain the context from the HTTP request.
    context_instance = RequestContext(request)

    try:
        user = _validate_and_get_geniuser(request)
    except LoggedInButFailedGetGeniUserError:
        return _show_failed_get_geniuser_page(request)

    sensors = []
    # Query the database for a list of ALL sensors currently stored.
    # Place the list in our context_dict dictionary which will be passed to the template engine.
    sensor_list = Sensor.objects.values()

    def zip_sa_data(sa_list):
        """
        Get a tupled list of Sensor Attribute ID and it's corresponding Sensor Attribute form
        """
        expsaforms = []
        for sa in sa_list:
            if request.method == "POST":
                esaf = ExperimentSensorAttributeForm(request.POST, prefix=str(sa['id']), label_suffix="", initial={'sensor_attribute': sa['id']}, instance=ExperimentSensorAttribute())
            else:
                esaf = ExperimentSensorAttributeForm(prefix=str(sa['id']), label_suffix="", initial={'sensor_attribute': sa['id']}, instance=ExperimentSensorAttribute())
            esaf.fields['sensor_attribute'].value = sa['id']
            esaf.fields['sa_select'].label = sa['name']
            esaf.fields['sa_select'].widget.attrs['data-label'] = sa['name']
            esaf.fields['sa_select'].widget.attrs['data-target'] = "#precision_div-"+str(sa['id'])
            expsaforms.append(esaf)

        return zip(sa_list, expsaforms)

    # List of Sensor ids
    s_id_list = Sensor.objects.values_list('id', flat=True).order_by('id')

    # Total list of SensorAttribute ids
    total_sa_id_list = SensorAttribute.objects.values_list('id', flat=True).order_by('id')

    # Populating sensor list with corresponding Sensor Attribute data
    for sensor in sensor_list:
        d = {'sensor': (sensor['id'], sensor['name'])}

        # A list of Sensor Attribute data which is later used to zip it with it's corresponding Sensor Attribute ID
        temp_list = []

        # A list of Sensor Attribute IDs which is later used to zip it with it's corresponding Sensor Attribute data list
        sa_id_list = []

        for sensorAtt in SensorAttribute.objects.filter(sensor_id=sensor['id']).values():
            temp_list.append((sensorAtt['id'], sensorAtt['name'], sensorAtt['precision_flag']))
            sa_id_list.append(sensorAtt['id'])
        # d['zipped_sa_data'] = zip_sa_data(temp_list, sa_id_list)
        d['zipped_sa_data'] = zip_sa_data(SensorAttribute.objects.filter(sensor_id=sensor['id']).values())
        sensors.append(d)

    # Only if the request method is POST
    if request.method == "POST":
        expform = ExperimentForm(request.POST, label_suffix="", instance=Experiment())
        expsensorforms = [ExperimentSensorForm(request.POST, prefix=str(x)) for x in s_id_list]
        expsaforms = [ExperimentSensorAttributeForm(request.POST, prefix=str(x)) for x in total_sa_id_list]

        # List of the valid sensor forms among the many empty forms submitted
        valid_esforms = []
        # List of the valid SensorAttribute forms among the many empty forms submitted
        valid_esaforms = []
        # List of the sensors selected through the form
        selected_sensors = []

        sa_sensors = []

        # To collect valid Sensor forms and corresponding sensor ids
        for esf in expsensorforms:
            if esf.has_changed():
                if esf.is_valid():
                    valid_esforms.append(esf)
                    # To get a list of unique sensors
                    if esf.cleaned_data['sensor'] not in selected_sensors:
                        selected_sensors.append(esf.cleaned_data['sensor'].id)

        # To collect VALID SensorAttribute forms and corresponding sensor_ids
        for esaf in expsaforms:
            # If user selected/changed data in this ExperimentSensorAttributeForm
            if esaf.has_changed():
                # If the ExperimentSensorAttributeForm is valid
                if esaf.is_valid():
                    sa = SensorAttribute.objects.select_related('sensor').get(pk=esaf.cleaned_data['sensor_attribute'].id)
                    valid_esaforms.append(esaf)
                    if sa.sensor.id in selected_sensors:
                        # valid_esaforms.append(esaf)
                        if sa.sensor.id not in sa_sensors:
                            sa_sensors.append(sa.sensor.id)

        # If all the forms are valid.. Just double checking..
        if expform.is_valid() and all([esf.is_valid() for esf in valid_esforms]) and all([esaf.is_valid() for esaf in valid_esaforms]):
            # If all the sensors from valid ExperimentSensorForms = All the sensors from valid ExperimentSensorAttributeForms, then save all the VALID forms
            if set(selected_sensors) == set(sa_sensors):
                new_exp = expform.save(commit=False)
                user_inst = GeniUser.objects.get(user_ptr_id=user.pk)
                new_exp.user = user_inst
                new_exp = expform.save()
                for esf in valid_esforms:
                    new_sensor = esf.save(commit=False)
                    new_sensor.experiment = new_exp
                    new_sensor.save()
                for esaf in valid_esaforms:
                    new_sa = esaf.save(commit=False)
                    new_sa.experiment = new_exp
                    new_sa.save()

                # messages.success(request, 'Experiment Submitted SUCCESSFULLY !!')
                # return HttpResponseRedirect('/html/expsuccess')
            # Generate an error message displaying which Sensor has corresponding unfilled Sensor Attribute forms
            else:
                for sensor in list(set(selected_sensors)-set(sa_sensors)):
                    s_obj = Sensor.objects.filter(id=sensor.id).values()
                    msg = "Need to select AT LEAST one sensor attribute under the sensor "+str(s_obj['name'])
                    messages.error(request, msg)
        # Generating error messages
        else:
            if not expform.is_valid():
                if expform.errors:
                    messages.error(request, expform.errors)
            for esf in valid_esforms:
                if not esf.is_valid():
                    if esf.errors:
                        messages.error(request, esf.errors)
            for esaf in valid_esaforms:
                if not esaf.is_valid():
                    if esaf.errors:
                        messages.error(request, esaf.errors)

        # If the submit fails, populating the forms with corresponding POST data to display it again
        if messages.error:
            expform = ExperimentForm(instance=Experiment(context_instance))
            expsensorforms = [ExperimentSensorForm(prefix=str(x), instance=ExperimentSensor(context_instance)) for x in s_id_list]
            expsaforms = [ExperimentSensorAttributeForm(prefix=str(x), instance=ExperimentSensorAttribute(context_instance)) for x in total_sa_id_list]

    # Generating new form for Experiment Registration
    else:
        expform = ExperimentForm(label_suffix="", instance=Experiment())

        expsensorforms = []
        for sensor in sensor_list:
            esf = ExperimentSensorForm(prefix=str(sensor['id']), label_suffix="", initial={'sensor': sensor['id']}, instance=ExperimentSensor())
            esf.fields['sensor'].value = sensor['id']
            esf.fields['sensor_select'].label = sensor['name']
            esf.fields['sensor_select'].widget.attrs['data-label'] = sensor['name']
            esf.fields['sensor_select'].widget.attrs['data-target'] = "#sensorattr-"+str(sensor['id'])
            expsensorforms.append(esf)

        # expsaforms = [ExperimentSensorAttributeForm(prefix=str(x), label_suffix="", instance=ExperimentSensorAttribute()) for x in total_sa_id_list]

    zipped_sensor_data = zip(sensors, expsensorforms)
    return render_to_response('control/expreg.html', {'zipped_sensor_data': zipped_sensor_data,'exp_sensor_forms':expsensorforms, 'username': user.username, 'exp_form': expform}, context_instance)


@login_required
def mygeni(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  total_vessel_credits = interface.get_total_vessel_credits(user)
  num_acquired_vessels = len(interface.get_acquired_vessels(user))
  avail_vessel_credits = interface.get_available_vessel_credits(user)
  
  if num_acquired_vessels > total_vessel_credits:
    percent_total_used = 100
    over_vessel_credits = num_acquired_vessels - total_vessel_credits
  else:
    percent_total_used = int((num_acquired_vessels * 1.0 / total_vessel_credits * 1.0) * 100.0)
    over_vessel_credits = 0
  
  # total_vessel_credits, percent_total_used, avail_vessel_credits
  return request_ro_response('control/mygeni.html',
                            {'username' : user.username,
                             'total_vessel_credits' : total_vessel_credits,
                             'used_vessel_credits' : num_acquired_vessels,
                             'percent_total_used' : percent_total_used,
                             'avail_vessel_credits' : avail_vessel_credits,
                             'over_vessel_credits' : over_vessel_credits},
                            context_instance=RequestContext(request))





@login_required
def myvessels(request, get_form=False, action_summary="", action_detail="", remove_summary=""):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # get_form of None means don't show the form to acquire vessels.
  if interface.get_available_vessel_credits(user) == 0:
    get_form = None
  elif get_form is False:
    get_form = forms.gen_get_form(user)

  # shared vessels that are used by others but which belong to this user (TODO)
  shvessels = []

  # this user's used vessels
  my_vessels_raw = interface.get_acquired_vessels(user)
  my_vessels = interface.get_vessel_infodict_list(my_vessels_raw)
  
  # this user's number of donations, max vessels, total vessels and free credits
  my_donations = interface.get_donations(user)
  my_max_vessels = interface.get_available_vessel_credits(user)	
  my_free_vessel_credits = interface.get_free_vessel_credits_amount(user)
  my_total_vessel_credits = interface.get_total_vessel_credits(user)

  for vessel in my_vessels:
    if vessel["expires_in_seconds"] <= 0:
      # We shouldn't ever get here, but just in case, let's handle it.
      vessel["expires_in"] = "Expired"
    else:
      days = vessel["expires_in_seconds"] / (3600 * 24)
      hours = vessel["expires_in_seconds"] / 3600 % 24
      minutes = vessel["expires_in_seconds"] / 60 % 60
      vessel["expires_in"] = "%dd %dh %dm" % (days, hours, minutes)

  # return the used resources page constructed from a template
  return render_to_response('control/myvessels.html',
                            {'username' : user.username,
                             'num_vessels' : len(my_vessels),
                             'my_vessels' : my_vessels,
                             'sh_vessels' : shvessels,
                             'get_form' : get_form,
                             'action_summary' : action_summary,
                             'action_detail' : action_detail,
                             'my_donations' : len(my_donations),
                             'my_max_vessels' : my_max_vessels, 
                             'free_vessel_credits' : my_free_vessel_credits,
                             'total_vessel_credits' : my_total_vessel_credits,
                             'remove_summary' : remove_summary},
                        context_instance=RequestContext(request))





@login_required
def getdonations(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  domain = "https://" + request.get_host()
  
  return render_to_response('control/getdonations.html',
                            {'username' : user.username,
                             'domain' : domain},
                            context_instance=RequestContext(request))





@login_required
def get_resources(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # the request must be via POST. if not, bounce user back to My Vessels page
  if not request.method == 'POST':
    return myvessels(request)
  
  # try and grab form from POST. if it can't, bounce user back to My Vessels page
  get_form = forms.gen_get_form(user, request.POST)
  
  action_summary = ""
  action_detail = ""
  keep_get_form = False
  
  if get_form.is_valid():
    vessel_num = get_form.cleaned_data['num']
    vessel_type = get_form.cleaned_data['env']
    
    try:
      acquired_vessels = interface.acquire_vessels(user, vessel_num, vessel_type)
    except UnableToAcquireResourcesError, err:
      action_summary = "Unable to acquire vessels at this time."
      if str(err) == 'Acquiring NAT vessels is currently disabled. ':
        link = """<a href="{{ TESTBED_URL }}}blog">blog</a>"""
        action_detail += str(err) + 'Please check our '+ link  +' to see when we have re-enabled NAT vessels.'
      else:
        action_detail += str(err)
      keep_get_form = True
    except InsufficientUserResourcesError:
      action_summary = "Unable to acquire vessels: you do not have enough vessel credits to fulfill this request."
      keep_get_form = True
  else:
    keep_get_form = True
  
  if keep_get_form == True:
    # return the original get_form, since the form wasn't valid (or there were errors)
    return myvessels(request, get_form, action_summary=action_summary, action_detail=action_detail)
  else:
    # return a My Vessels page with the updated vessels/vessel acquire details/errors
    return myvessels(request, False, action_summary=action_summary, action_detail=action_detail)
  
  
  
  

@login_required
def del_resource(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # the request must be via POST. if not, bounce user back to My Vessels page
  if not request.method == 'POST':
    return myvessels(request)

  if not request.POST['handle']:
    return myvessels(request)
  
  # vessel_handle needs to be a list (even though we only add one handle), 
  # since get_vessel_list expects a list.
  vessel_handle = []
  vessel_handle.append(request.POST['handle'])
  remove_summary = ""
  
  try:
    # convert handle to vessel
    vessel_to_release = interface.get_vessel_list(vessel_handle)
  except DoesNotExistError:
    remove_summary = "Unable to remove vessel. The vessel you are trying to remove does not exist."
  except InvalidRequestError, err:
    remove_summary = "Unable to remove vessel. " + str(err)
  else:
    try:
      interface.release_vessels(user, vessel_to_release)
    except InvalidRequestError, err:
      remove_summary = "Unable to remove vessel. The vessel does not belong"
      remove_summary += " to you any more (maybe it expired?). " + str(err)
  
  return myvessels(request, remove_summary=remove_summary)






@login_required
def del_all_resources(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # the request must be via POST. if not, bounce user back to My Vessels page
  if not request.method == 'POST':
    return myvessels(request)
  
  remove_summary = ""

  try:
    interface.release_all_vessels(user)
  except InvalidRequestError, err:
    remove_summary = "Unable to release all vessels: " + str(err)
  
  return myvessels(request, remove_summary=remove_summary)






@login_required
def renew_resource(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # The request must be via POST. If not, bounce user back to My Vessels page.
  if not request.method == 'POST':
    return myvessels(request)
  
  if not request.POST.get('handle', ''):
    return myvessels(request)
  
  action_summary = ""
  action_detail = ""
  
  try:
    # Convert handle to vessel object.
    # Raises a DoesNotExistError if the vessel does not exist. This is more
    # likely to be an error than an expected case, so we let it bubble up.
    vessel_handle_list = [request.POST['handle']]
    vessel_to_renew = interface.get_vessel_list(vessel_handle_list)
  except DoesNotExistError:
    action_summary = "Unable to renew vessel: The vessel you are trying to delete does not exist."
  except InvalidRequestError, err:
    action_summary = "Unable to renew vessel."
    action_detail += str(err)
  else:
    try:
      interface.renew_vessels(user, vessel_to_renew)
    except InvalidRequestError, err:
      action_summary = "Unable to renew vessel: " + str(err)
    except InsufficientUserResourcesError, err:
      action_summary = "Unable to renew vessel: you are currently over your"
      action_summary += " vessel credit limit."
      action_detail += str(err)
  
  return myvessels(request, False, action_summary=action_summary, action_detail=action_detail)





@login_required
def renew_all_resources(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  # The request must be via POST. If not, bounce user back to My Vessels page.
  if not request.method == 'POST':
    return myvessels(request)
  
  action_summary = ""
  action_detail = ""
  
  try:
    interface.renew_all_vessels(user)
  except InvalidRequestError, err:
    action_summary = "Unable to renew vessels: " + str(err)
  except InsufficientUserResourcesError, err:
    action_summary = "Unable to renew vessels: you are currently over your"
    action_summary += " vessel credit limit."
    action_detail += str(err)
  
  return myvessels(request, False, action_summary=action_summary, action_detail=action_detail)





@login_required
def change_key(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  info = ""
  if request.method == 'GET':
    return render_to_response('control/change_key.html',
                              {'username' : user.username,
                               'error_msg' : ""},
                              context_instance=RequestContext(request))

  # This is a POST, so figure out if a file was uploaded or if we are supposed
  # to generate a new key for the user.
  if request.POST.get('generate', False):
    interface.change_user_keys(user, pubkey=None)
    msg = "Your new keys have been generated. You should download them now."
    return profile(request, msg)
    
  else:
    file = request.FILES.get('pubkey', None)
    if file is None:
      msg = "You didn't select a public key file to upload." 
      return profile(request, info, msg)

    
    if file.size == 0 or file.size > forms.MAX_PUBKEY_UPLOAD_SIZE:
      msg = "Invalid file uploaded. The file size limit is " 
      msg += str(forms.MAX_PUBKEY_UPLOAD_SIZE) + " bytes."
      return profile(request, info, msg) 
          
    pubkey = file.read()
    
    try:
      validations.validate_pubkey_string(pubkey)
    except ValidationError:
      msg = "Invalid public key uploaded."
      return profile(request, info, msg)
    
    # If we made it here, the uploaded key is good.
    interface.change_user_keys(user, pubkey=pubkey)
    msg = "Your public key has been successfully changed."
    return profile(request, msg)





@login_required
def api_info(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  if request.method == 'GET':
    return render_to_response('control/api_info.html',
                              {'username' : user.username,
                               'api_key' : user.api_key,
                               'msg' : ""},
                              context_instance=RequestContext(request))

  # This is a POST, so it should be generation of an API key.
  if not request.POST.get('generate_api_key', False):
    msg = "Sorry, we didn't understand your request."
    return profile(request, info, msg) 
    
  interface.regenerate_api_key(user)
  msg = "Your API key has been regenerated. Your old one will no longer work."
  msg += " You should update any places you are using the API key"
  msg += " (e.g. in programs using the XML-RPC client)."
  return profile(request,msg)





@log_function_call
@require_POST
@login_required
def del_priv(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  if user.user_privkey == "":
    msg = "Your private key has already been deleted."
  else:
    interface.delete_private_key(user)
    msg = "Your private key has been deleted."
  return profile(request, msg)





@log_function_call
@login_required
def priv_key(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  response = HttpResponse(user.user_privkey, mimetype='text/plain')
  response['Content-Disposition'] = 'attachment; filename=' + \
          str(user.username) + '.privatekey'
  return response





@log_function_call
@login_required
def pub_key(request):
  try:
    user = _validate_and_get_geniuser(request)
  except LoggedInButFailedGetGeniUserError:
    return _show_failed_get_geniuser_page(request)
  
  response = HttpResponse(user.user_pubkey, mimetype='text/plain')
  response['Content-Disposition'] = 'attachment; filename=' + \
            str(user.username) + '.publickey'
  return response





def download(request, username):
  validuser = True
  try:
    # validate that this username actually exists
    user = interface.get_user_for_installers(username)
  except DoesNotExistError:
    validuser = False

  templatedict = {}
  templatedict['username'] = username
  templatedict['validuser'] = validuser
  templatedict['domain'] = "https://" + request.get_host()
  # I need to build a URL for android to download the installer from.   (The
  # same installer is downloaded from the Google Play store for all users.) 
  # The URL is escaped twice (ask Akos why) and inserted in the referrer 
  # information in the URL.   
  #templatedict['android_installer_link'] = urllib.quote(urllib.quote(domain,safe=''),safe='')

  return render_to_response('download/installers.html', templatedict,
          context_instance=RequestContext(request))





def build_android_installer(request, username):
  """
  <Purpose>
    Allows the user to download a Android distribution of Seattle that will
    donate resources to user with 'username'.
  
  <Arguments>
    request:
      Django HttpRequest object
       
    username:
      A string representing the GENI user to which the installer will donate
      resources.
  
  <Exceptions>
    None
  
  <Side Effects>
    None
  
  <Returns>
    On failure, returns an HTTP response with a description of the error. On
    success, redirects the user to download the installer.
  """
  
  success, return_value = _build_installer(username, "android")
  
  if not success:
    error_response = return_value
    return error_response
  
  installer_url = return_value
  return HttpResponseRedirect(installer_url)





def build_win_installer(request, username):
  """
  <Purpose>
    Allows the user to download a Windows distribution of Seattle that will
    donate resources to user with 'username'.
  
  <Arguments>
    request:
      Django HttpRequest object
       
    username:
      A string representing the GENI user to which the installer will donate
      resources.
  
  <Exceptions>
    None
  
  <Side Effects>
    None
  
  <Returns>
    On failure, returns an HTTP response with a description of the error. On
    success, redirects the user to download the installer.
  """
  
  success, return_value = _build_installer(username, "windows")
  
  if not success:
    error_response = return_value
    return error_response
  
  installer_url = return_value
  return HttpResponseRedirect(installer_url)





def build_linux_installer(request, username):
  """
  <Purpose>
    Allows the user to download a Linux distribution of Seattle that will
    donate resources to user with 'username'.

  <Arguments>
    request:
      Django HttpRequest object

    username:
      A string representing the GENI user to which the installer will donate
      resources.

  <Exceptions>
    None

  <Side Effects>
    None

  <Returns>
    On failure, returns an HTTP response with a description of the error. On
    success, redirects the user to download the installer.
  """

  success, return_value = _build_installer(username, "linux")

  if not success:
    error_response = return_value
    return error_response

  installer_url = return_value
  return HttpResponseRedirect(installer_url)





def build_mac_installer(request, username):
  """
  <Purpose>
    Allows the user to download a Mac distribution of Seattle that will
    donate resources to user with 'username'.

  <Arguments>
    request:
      Django HttpRequest object

    username:
      A string representing the GENI user to which the installer will donate
      resources.

  <Exceptions>
    None

  <Side Effects>
    None

  <Returns>
    On failure, returns an HTTP response with a description of the error. On
    success, redirects the user to download the installer.
  """

  success, return_value = _build_installer(username, "mac")

  if not success:
    error_response = return_value
    return error_response

  installer_url = return_value
  return HttpResponseRedirect(installer_url)





def _build_installer(username, platform):
  """
  <Purpose>
    Builds an installer for the given platform that will donate resources to
    the user with the given username.
  
  <Arguments>
    username:
      A string representing the GENI user to which the installer will donate
      resources.
      
    platform:
      A string representing the platform for which to build the installer.
      Options include 'windows', 'linux', or 'mac'.
  
  <Exceptions>
    None
  
  <Side Effects>
    None
  
  <Returns>
    On success, returns (True, installer_url) where installer_url is URL from
    which the installer may be downloaded.
    
    On failure, returns (False, error_response) where error_repsponse is an
    HttpResponse which specifies what went wrong.
  """
  try:
    user = interface.get_user_for_installers(username)
    username = user.username
  except DoesNotExistError:
    error_response = HttpResponse("Couldn't get user.")
    return False, error_response

  try:
    xmlrpc_proxy = xmlrpclib.ServerProxy(settings.SEATTLECLEARINGHOUSE_INSTALLER_BUILDER_XMLRPC)
    
    vessel_list = [{'percentage': 80, 'owner': 'owner', 'users': ['user']}]
    
    user_data = {
      'owner': {'public_key': user.donor_pubkey},
      'user': {'public_key': ACCEPTDONATIONS_STATE_PUBKEY},
    }
    
    build_results = xmlrpc_proxy.build_installers(vessel_list, user_data)
  except:
    error_response = HttpResponse("Failed to build installer.")
    return False, error_response

  installer_url = build_results['installers'][platform]
  return True, installer_url





def donations_help(request, username):
  return render_to_response('download/help.html', {'username' : username},
          context_instance=RequestContext(request))





def _validate_and_get_geniuser(request):
  try:
    user = interface.get_logged_in_user(request)
  except DoesNotExistError:
    # Failed to get GeniUser record, but user is logged in
    raise LoggedInButFailedGetGeniUserError
  return user





@log_function_call_without_return
@login_required
def new_auto_register_user(request):
  msg = "Your account has been succesfully created. "
  msg += "If you would like to login without OpenID/OAuth please change your password now."
  return profile(request,msg)





def _show_failed_get_geniuser_page(request):
  err = "Sorry, we can't display the page you requested. "
  err += "If you are logged in as an administrator, you'll need to logout, and login with a Seattle Clearinghouse account. "
  err += "If you aren't logged in as an administrator, then this is a bug. Please contact us!"
  return _show_login(request, 'accounts/login.html', {'err' : err})



