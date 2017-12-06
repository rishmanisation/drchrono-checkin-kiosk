# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, render_to_response
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic import View, TemplateView, FormView
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, get_user_model, login, logout

from .forms import PatientSignInForm, PatientDemographicsForm
from .models import Appointment
from .api_access import API_Access
from .shortcuts import Shortcuts

from dateutil import parser
import datetime

def get_user_access_token(user):
    return user.social_auth.get(provider='drchrono').extra_data['access_token']

# Create your views here.
class CheckInView(View):
    form_class = PatientSignInForm
    template_name = 'checkin_kiosk/checkin_page.html'

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        context = {
            'form': form
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        api_request = API_Access(get_user_access_token(request.user))
        form = self.form_class(request.POST)
        if form.is_valid():
            clean = form.cleaned_data
            first_name = clean['firstname']
            last_name = clean['lastname']
            patient_id = api_request.get_patient_id(firstname=first_name, lastname=last_name)
            if patient_id is None:
                context = {
                    'form': form,
                    'cred': Shortcuts.Validations.INVALID_CREDENTIALS
                }
                return render(request, self.template_name, context)

            else:
                response = api_request.get_appointments_by_patient_name(
                    firstname=first_name, 
                    lastname=last_name,
                    info_present=False
                )
                print response
                context = {
                    'form': form,
                    'appointment_details': response,
                    'patient_id': patient_id
                }
                return render(request, self.template_name, context)

        context = {
            'form': form
        }
        return render(request, self.template_name, context)

class DemographicsFormView(FormView):
    print '1'
    form_class = PatientDemographicsForm
    template_name = 'checkin_kiosk/demographics.html'

    def dispatch(self, request, *args, **kwargs):
        print '2'
        self.api_access = API_Access(get_user_access_token(request.user))
        self.patient_id = int(self.kwargs['patient_id'])
        self.patient_info = self.api_access.get_patient_information(self.patient_id)
        return super(DemographicsFormView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        print '3'
        context = super(DemographicsFormView, self).get_context_data(**kwargs)
        context['patient_info'] = self.patient_info
        return context

    def get_initial(self):
        print '4'
        return self.patient_info

    def form_valid(self, form):
        print '5'
        data = form.cleaned_data
        doctor_id = self.patient_info['doctor']
        data.update({
            'doctor': doctor_id
        })
        self.patient_updated_info = self.api_access.edit_patient_information(self.patient_id, data)
        name = data['first_name'] + ' ' + data['last_name']
        if self.patient_updated_info.status_code != Shortcuts.ErrorCodes.SUCCESS:
            print 'Error updating patient info'
            return HttpResponseRedirect(reverse('demographic_form', args=[self.patient_id]))

        else:
            self.appointment = self.api_access.get_appointments_by_patient_name(
                firstname = data['first_name'],
                lastname = data['last_name'],
                info_present = True
            )
            appointment_id = self.appointment['id']
            self.appointment['status'] = Shortcuts.Statuses.ARRIVED
            response = self.api_access.edit_appointment_information(appointment_id, self.appointment)
            if response.status_code != Shortcuts.ErrorCodes.SUCCESS:
                print 'Error updating appointment info'
                return HttpResponseRedirect(reverse('demographic_form', args=[self.patient_id]))

            else:
                appointment_obj = Appointment.objects.get(
                    appointment_id=appointment_id,
                    patient_id=str(self.patient_id)
                )
                if not appointment_obj:
                    appointment_object = Appointment(
                        name=name,
                        appointment_id=appointment_id,
                        patient_id=self.patient_id,
                        status=Shortcuts.Statuses.ARRIVED,
                        appointment_start_time=parser.parse(self.appointment['scheduled_time']),
                        duration = self.appointment['duration']
                    )
                    try:
                        appointment_object.save()
                    except Exception as e:
                        return HttpResponseRedirect(reverse('demographic_form', args=[self.patient_id]))
                
                else:
                    appointment_obj.status = Shortcuts.Statuses.ARRIVED
                    appointment_obj.start_time = parser.parse(self.appointment['scheduled_time'])
                    appointment_obj.duration = self.appointment['duration']
                    appointment_obj.status_time = datetime.datetime.now()
                    appointment_obj.save()
            
                return HttpResponseRedirect(reverse('success', args=[self.appointment['office']]))
    
class SuccessView(View):
    template_name = 'checkin_kiosk/success.html'
    
    def get(self, request, *args, **kwargs):
        room_id = kwargs['room_id']
        context = {
            'room_id': room_id
        }
        return render(request, self.template_name, context)





        
        

