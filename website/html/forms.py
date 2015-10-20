"""
<Program Name>
  forms.py

<Started>
  October, 2008

<Author>
  Ivan Beschastnikh
  ivan@cs.washington.edu
  
  Jason Chen
  jchen@cs.washington.edu

  Sai Kaushik Borra
  skb386@nyu.edu
<Purpose>

<Usage>
  For more information on forms in django see:
  http://docs.djangoproject.com/en/dev/topics/forms/
"""

# from clearinghouse.website.control.models import GeniUser, Sensors, SensorAttributes
from clearinghouse.website.control.models import GeniUser, Sensor, SensorAttribute, Experiment, ExperimentSensor, ExperimentSensorAttribute
# from control.models import GeniUser, Sensor, SensorAttribute, Experiment, ExperimentSensor, ExperimentSensorAttribute

from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
import django.forms as forms

# from clearinghouse.common.exceptions import *
# from clearinghouse.common.util import validations
# from clearinghouse.website.control import interface

from common.exceptions import *
from common.util import validations
from clearinghouse.website.control import interface


MAX_PUBKEY_UPLOAD_SIZE = 2048


class PubKeyField(forms.FileField):
    def clean(self, value, initial):
        forms.FileField.clean(self, value, initial)
        if value is None:
            return None
        if value.size > MAX_PUBKEY_UPLOAD_SIZE:
            raise forms.ValidationError, "Public key too large, file size limit is " + str(MAX_PUBKEY_UPLOAD_SIZE) + " bytes"
            # get the pubkey out of the uploaded file
        pubkey = value.read()
        try:
            validations.validate_pubkey_string(pubkey)
        except ValidationError, err:
            raise forms.ValidationError, str(err)
        return pubkey

class ExperimentForm(forms.ModelForm):
    name = forms.CharField(label="Name of the Experiment",
                           error_messages={'required': 'Enter the name of the experiment'},
                           widget=forms.TextInput(attrs={'class': 'form-control',
                                                         'placeholder': 'Enter the Name of your Experiment'}))

    researcher_name = forms.CharField(label="Name of the Researcher",
                           error_messages={'required': 'Enter the name of the Researcher'},
                           widget=forms.TextInput(attrs={'class': 'form-control',
                                                         'placeholder': 'Enter the Name of the Researcher'}))

    researcher_address = forms.CharField(label="Name and address of Researcher\'s home institution",
                                         widget=forms.TextInput(attrs={'class': 'form-control',
                                                         'placeholder': 'Enter the Address of the Researcher\'s home institution'}),
                                         error_messages={'required': 'Enter the address of the Researcher\'s home institution'})

    researcher_email = forms.EmailField(label="Researcher\'s E-mail Address",
                                        widget=forms.EmailInput(attrs={'class': 'form-control',
                                            'placeholder': 'Enter Researcher\'s E-mail Address',
                                            'pattern': "(?!(^[.-].*|[^@]*[.-]@|.*\.{2,}.*)|^.{254}.)([a-zA-Z0-9!#$%&'*+\/=?^_`{|}~.-]+@)(?!-.*|.*-\.)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,15}"}),
                                        error_messages={'required': 'Enter Researchers E-mail Address'})

    irb_officer_name = forms.CharField(label="Name of the home institution\'s IRB officer or contact person",
                                       widget=forms.TextInput(attrs={'class': 'form-control',
                                                         'placeholder': 'Enter the Name of your Experiment'}),
                                       error_messages={'required': 'Enter Contact Person\'s Name'})

    irb_officer_email = forms.EmailField(label="Email address of home institution\'s IRB officer or contact person",
                                        widget=forms.EmailInput(attrs={'class': 'form-control',
                                            'placeholder': 'Enter the Email Address of your contact person',
                                            'pattern': "(?!(^[.-].*|[^@]*[.-]@|.*\.{2,}.*)|^.{254}.)([a-zA-Z0-9!#$%&'*+\/=?^_`{|}~.-]+@)(?!-.*|.*-\.)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,15}"}),
                                        error_messages={'required': 'Enter contact person\'s E-mail Address'})

    goal = forms.CharField(label="What is the goal of your research experiment? What do you want to find out?",
                           widget=forms.Textarea(attrs={'class': 'form-control', 'rows':1,
                                                         'placeholder': 'Enter the goal of your Experiment'}),
                           error_messages={'required': 'Enter the goal of your research experiment'},
                           max_length=256)

    sensor_other = forms.CharField(label='If you find sensors that we DO NOT support, please tell us more',
                                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows':1,
                                                         'placeholder': 'Enter the names of sensors and relevant information'}),
                                    required=False,
                                    max_length=256)

    store_protect = forms.CharField(label='How and where will you store and protect the collected data?',
                                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows':1,
                                                         'placeholder': 'Enter how do you plan to store and protect the collected data'}),
                                    error_messages={'required': 'Please fill in - How and where will you store and protect the collected data'},
                                    max_length=512)
    class Meta:
        model = Experiment
        exclude = ('user',)

class ExperimentSensorForm(forms.ModelForm):
    sensor_select = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'sensors collapsible'}))
    frequency = forms.IntegerField(label='Once every', min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    F_CHOICES = (('hour', 'Hour'),('min', 'Min'),('sec', 'Sec'),)
    frequency_unit = forms.ChoiceField(widget = forms.Select(attrs={'class': 'form-control'}),
                     choices = F_CHOICES, initial='hour', required = True,)
    frequency_other = forms.CharField(label="Other:", required=False,
                                        widget=forms.TextInput(attrs={'class': 'form-control',
                                                'placeholder': 'Please provide any additional information that you would like'}))
    precision_other = forms.CharField(label="A level of data precision that we currently do not support? Please elaborate:", required=False,
                                        widget=forms.Textarea(attrs={'class': 'form-control', 'rows':1,
                                                'placeholder': 'Please provide any additional information that you would like'}))
    D_CHOICES = ((1, 'Yes',), (0, 'No',))
    downloadable = forms.ChoiceField(label= "Will these sensor data be downloaded from participant\'s devices?",                                                                                                                                      widget=forms.RadioSelect, choices=D_CHOICES)
    usage_policy = forms.CharField(label='What will these sensor data be used for?',
                                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows':1,
                                                         'placeholder': 'Enter how do you plan to use the collected data'}),
                                    max_length=512)
    class Meta:
        model = ExperimentSensor
        exclude = ('experiment',)

    def clean(self):
        data = super(ExperimentSensorForm, self).clean()
        if data.get('sensor_select'):
            if data.get('sensor'):
                frequency = data.get('frequency')
                if frequency:
                    if data['frequency_unit']=='hour':
                        data['frequency'] = frequency*60*60
                    elif data['frequency_unit']=='min':
                        data['frequency'] =  frequency*60

            if data.get('frequency') or data.get('frequency_other'):
                # print("##############")
                # print(data)
                # print("##############")
                return data
            else:
                raise ValidationError('Please fill in either of the fields under '+Sensor.objects.filter(id=data.get('sensor')).name)
        
        return data

class ExperimentSensorAttributeForm(forms.ModelForm):
    sa_select = forms.BooleanField(widget=forms.CheckboxInput(attrs={'class': 'sa collapsible'}))
    P_CHOICES = (('full', 'Full Precision'),('truncate', 'Truncate'),)
    precision_choice = forms.ChoiceField(widget = forms.Select(),
                     choices = P_CHOICES, required = False,)
    PL_CHOICES = ((1, 'City'),(10, 'State'),(11, 'Country'),)
    precision_choice_loc = forms.ChoiceField(label= "Level of Blurring",
        widget = forms.Select(attrs={'class': 'form-control'}),
                     choices = PL_CHOICES, required = False,)
    precision = forms.IntegerField(required=False,)

    class Meta:
        model = ExperimentSensorAttribute
        exclude = ('experiment',)

    def clean(self):
        data = super(ExperimentSensorAttributeForm, self).clean()
        # Validate and process precision data for a selected sensor_attribute
        # Check if the precision Attribute is applicable for the given Sensor Attribute
        # print('@@@@@@@@@@@@@@@')
        # print(data)

        if data.get('sa_select'):
            if data.get('sensor_attribute'):
                # data['sensor_attribute'] = data.get('sensor_attribute').id

                if data.get('precision_choice_loc'):
                    precision = data.get('precision_choice_loc')
                elif data.get('precision'):
                    precision = data.get('precision')

                if data['precision_choice'] == 'full':
                    data['precision'] = 0
                elif data['precision_choice'] == 'truncate':
                    if precision:
                        data['precision'] = precision
                    else:
                        raise ValidationError('Please fill in truncation level under '+SensorAttribute.objects.filter(id=data['sensor_attribute']).name)
                else:
                    data['precision'] = 0
                    # raise ValidationError('Please provide truncation data under '+SensorAttribute.objects.filter(id=data['sensor_attribute']).name)
                data['precision_choice'] = None
        else:
            # If NOT applicable, set everything to None
            data['precision_choice'] = None
            data['precision'] = None
        return data

class GeniUserCreationForm(DjangoUserCreationForm):
    affiliation = forms.CharField(error_messages={'required': 'Enter an Affiliation'})
    email = forms.CharField(label="E-mail Address", error_messages={'required': 'Enter an E-mail Address'})
    pubkey = PubKeyField(label="My Public Key", required=False)
    gen_upload_choice = forms.ChoiceField(label="", choices=((1, 'Generate key pairs for me'), (2, 'Let me upload my public key')))
    username = forms.CharField(label="Username", error_messages={'required': 'Enter a username'}, max_length=validations.USERNAME_MAX_LENGTH)

    def __init__(self, *args):
        DjangoUserCreationForm.__init__(self, *args)
        #self.fields['username'].error_messages['required'] = 'Enter a username'
        self.fields['password1'].error_messages['required'] = 'Enter a password'
        self.fields['password2'].error_messages['required'] = 'Verify your password'

    def clean_username(self):
        value = self.cleaned_data['username']
        try:
            validations.validate_username(value)
        except ValidationError, err:
            raise forms.ValidationError, str(err)
        return value

    def clean_password1(self):
        value = self.cleaned_data['password1']
        try:
            validations.validate_password(value)
        except ValidationError, err:
            raise forms.ValidationError, str(err)
        return value

    def clean_affiliation(self):
        value = self.cleaned_data['affiliation']
        try:
            validations.validate_affiliation(value)
        except ValidationError, err:
            raise forms.ValidationError, str(err)
        return value

    def clean_email(self):
        value = self.cleaned_data['email']
        try:
            validations.validate_email(value)
        except ValidationError, err:
            raise forms.ValidationError, str(err)
        return value

def gen_edit_user_form(field_list=None, *args, **kwargs):
  """
  <Purpose>
      Dynamically generates a EditUserForm depending on field_list.

  <Arguments>
      field_list:
          The profile view passes in the desired field that will be edited by the
          EditUserForm.

  <Exceptions>
      ValidationErrors raised by a incorrect field value.

  <Side Effects>
      None.

  <Returns>
      A EditUserForm object that is specific to the field list passed in.

  """
  class EditUserForm(forms.ModelForm):
    class Meta:
      model = GeniUser
      fields = field_list
      
    def __init__(self):
      super(EditUserForm, self).__init__(*args, **kwargs)
      
    def clean_affiliation(self):
      value = self.cleaned_data['affiliation']
      try:
        validations.validate_affiliation(value)
      except ValidationError, err:
        raise forms.ValidationError, str(err)
      return value
      
    def clean_email(self):
      value = self.cleaned_data['email']
      try:
        validations.validate_email(value)
      except ValidationError, err:
        raise forms.ValidationError, str(err)
      return value
    
  return EditUserForm()

class EditUserPasswordForm(forms.ModelForm):
  password1 = forms.CharField(label=("Password"), required=False, widget=forms.PasswordInput)
  password2 = forms.CharField(label=("Password confirmation"), required=False, widget=forms.PasswordInput, help_text = ("Enter the same password as above, for verification."))
  class Meta:
    model = GeniUser
    fields = ('password1','password2')
    
  def clean(self):
    data = self.cleaned_data
    if data['password1'] != data['password2']:
      raise forms.ValidationError(("The two password fields didn't match."))
    try:
      validations.validate_password(data['password1'])
    except ValidationError, err:
      raise forms.ValidationError, str(err)
    return data

class AutoRegisterForm(forms.ModelForm):
  username = forms.CharField(label="Username", error_messages={'required': 'Enter a username'}, max_length=validations.USERNAME_MAX_LENGTH)
  class Meta:
    model = GeniUser
    fields = ('username',)

  def clean_username(self):
    value = self.cleaned_data['username']
    try:
      validations.validate_username(value)
    except ValidationError, err:
      raise forms.ValidationError, str(err)
    return value
  
  '''    
  def clean(self):
    data = self.cleaned_data
    try:
      validations.validate_username(data['username'])
    except ValidationError, err:
      raise forms.ValidationError, str(err)
    return data    
  '''    





def gen_get_form(geni_user, req_post=None):
  """
  <Purpose>
      Dynamically generates a GetVesselsForm that has the right
      number vessels (the allowed number of vessels a user may
      acquire). Possibly generate a GetVesselsForm from an HTTP POST
      request.

  <Arguments>
      geni_user:
          geni_user object
      req_post:
          An HTTP POST request (django) object from which a
          GetVesselsForm may be instantiated. If this argument is
          not supplied, a blank form will be created

  <Exceptions>
      None.

  <Side Effects>
      None.

  <Returns>
      A GetVesselsForm object that is instantiated with a req_post
      (if given).
  """
      
  # the total number of vessels a user may acquire
  avail_vessel_credits = interface.get_available_vessel_credits(geni_user)
  
  # Dynamic generation of the options for numbers the user can request based
  # on their number of available vessel credits.
  if avail_vessel_credits == 0:
    step = [0]
  elif avail_vessel_credits < 10:
    step = range(1, avail_vessel_credits+1)
  elif avail_vessel_credits < 100:
    step = range(1, 10)
    step.extend(range(10, avail_vessel_credits+1,10))
  else:
    step = range(1, 10)
    step.extend(range(10, 101,10))
    step.extend(range(200, avail_vessel_credits+1, 100))
    
  if avail_vessel_credits not in step:
    step.append(avail_vessel_credits)

  # dynamically generate the get vessels form
  #get_vessel_choices = zip(range(1,max_num+1),range(1,max_num+1))
  get_vessel_choices = zip(step, step)
  
  # This is ugly (nested class definition, that is) and appears to have been
  # done as a way to avoid using a constructor but still make the value of
  # get_vessel_choices available to instances of this class.
  class GetVesselsForm(forms.Form):
    """
    <Purpose>
        Generates a form to acquire vessels by the user
    <Side Effects>
        None
    <Example Use>
        GetVesselsForm()
            to generate a blank form
        GetVesselsForm(post_request)
            to generate a form from an existing POST request
    """
    # maximum number of vessels a user is allowed to acquire
    #num = forms.ChoiceField(choices=get_vessel_choices, error_messages={'required' : 'Please enter the number of vessels to acquire'})
    num = forms.ChoiceField(choices=get_vessel_choices)
    
    # the various environment types the user may select from
    #env = forms.ChoiceField(choices=((1,'LAN'),(2,'WAN'),(3,'Random')), error_messages={'required' : 'Please enter the networking environment for vessels to acquire'})
    env = forms.ChoiceField(choices=(('wan','WAN'),('lan','LAN'),('nat','NAT'),('rand','Random')))
    
    def clean_num(self):
      value = int(self.cleaned_data['num'])
      if value < 1:
        raise forms.ValidationError("Invalid vessel number selection.")
      return value
    
    def clean_env(self):
      value = str(self.cleaned_data['env'])
      if not (value == 'wan' or value == 'lan' or value == 'nat' or value == 'rand'):
        raise forms.ValidationError("Invalid vessel type selection.")
      return value
    
    def get_errors_as_str(self):
      return str(self.errors)
  
  if req_post is None:
      return GetVesselsForm()
  return GetVesselsForm(req_post)
