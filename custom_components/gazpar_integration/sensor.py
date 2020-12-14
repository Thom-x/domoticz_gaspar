"""Platform for sensor integration."""
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity
import base64
import requests
import html
import sys
import os
import re
import logging
from lxml import etree
import xml.etree.ElementTree as ElementTree
import io
import json
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_NAME
)


SCAN_INTERVAL = timedelta(minutes=30)
LOGIN_BASE_URI = 'https://monespace.grdf.fr/web/guest/monespace'
API_BASE_URI = 'https://monespace.grdf.fr/monespace/particulier'
API_ENDPOINT_LOGIN = '?p_p_id=EspacePerso_WAR_EPportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-2&p_p_col_count=1&_EspacePerso_WAR_EPportlet__jsfBridgeAjax=true&_EspacePerso_WAR_EPportlet__facesViewIdResource=%2Fviews%2FespacePerso%2FseconnecterEspaceViewMode.xhtml'
API_ENDPOINT_HOME = '/accueil'
API_ENDPOINT_DATA = '/consommation/tableau-de-bord'
DATA_NOT_REQUESTED = -1
DATA_NOT_AVAILABLE = -2

DEFAULT_NAME = "Compteur Gazpar"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_EMAIL): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    add_entities([GazparSensor(config)])


class GazparSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, config):
        """Initialize the sensor."""
        self._name = config.get(CONF_NAME)
        self._username = config.get(CONF_EMAIL)
        self._password = config.get(CONF_PASSWORD)
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    def update(self):
        token = self.login(self._username, self._password)
        today = datetime.date.today()
        res_month = self.get_data_per_month(token, self.dtostr(today - relativedelta(months=11)), self.dtostr(today))
        res_day = self.get_data_per_day(token, self.dtostr(today - relativedelta(days=1, months=1)), self.dtostr(today - relativedelta(days=1)))
        self._state = res_day[-1]["conso"]

    def parse_lxml(self, c):
        root = etree.fromstring(c)
        log=root.xpath("//update[@id = 'javax.faces.ViewState']")
        return(log[0].text)

    def login(self, username, password):
        session = requests.Session()

        payload = {
                   'javax.faces.partial.ajax': 'true',
                   'javax.faces.source': '_EspacePerso_WAR_EPportlet_:seConnecterForm:meConnecter',
                   'javax.faces.partial.execute': '_EspacePerso_WAR_EPportlet_:seConnecterForm',
                   'javax.faces.partial.render': 'EspacePerso_WAR_EPportlet_:global _EspacePerso_WAR_EPportlet_:groupTitre',
                   'javax.faces.behavior.event': 'click',
                   'javax.faces.partial.event': 'click',
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm': '_EspacePerso_WAR_EPportlet_:seConnecterForm',
                   'javax.faces.encodedURL': 'https://monespace.grdf.fr/web/guest/monespace?p_p_id=EspacePerso_WAR_EPportlet&amp;p_p_lifecycle=2&amp;p_p_state=normal&amp;p_p_mode=view&amp;p_p_cacheability=cacheLevelPage&amp;p_p_col_id=column-2&amp;p_p_col_count=1&amp;_EspacePerso_WAR_EPportlet__jsfBridgeAjax=true&amp;_EspacePerso_WAR_EPportlet__facesViewIdResource=%2Fviews%2FespacePerso%2FseconnecterEspaceViewMode.xhtml',
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm:email': username,
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm:passwordSecretSeConnecter': password
                   }

        session.headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Mobile Safari/537.36',
                    'Accept-Language':'fr,fr-FR;q=0.8,en;q=0.6',
                    'Accept-Encoding':'gzip, deflate, br', 
                    'Accept':'application/xml, application/json, text/javascript, */*; q=0.01',
                    'Faces-Request':'partial/ajax',
                    'Sec-Fetch-Mode':'no-cors',
                    'Sec-Fetch-Site':'same-origin',
                    'Origin':'https://monespace.grdf.fr',
                    'Referer':'https://monespace.grdf.fr/monespace/connexion'}

        session.cookies['KPISavedRef'] ='https://monespace.grdf.fr/monespace/connexion'

        session.get(LOGIN_BASE_URI + API_ENDPOINT_LOGIN, verify=False, timeout=None, data=payload, allow_redirects=False)
        
        req = session.post(LOGIN_BASE_URI + API_ENDPOINT_LOGIN, data=payload, allow_redirects=False)

        javaxvs2=self.parse_lxml(req.text)

        self._javavxs=javaxvs2

        #2nd request
        payload = {
                   'javax.faces.partial.ajax': 'true',
                   'javax.faces.source': '_EspacePerso_WAR_EPportlet_:seConnecterForm:meConnecter',
                   'javax.faces.partial.execute': '_EspacePerso_WAR_EPportlet_:seConnecterForm',
                   'javax.faces.partial.render': 'EspacePerso_WAR_EPportlet_:global _EspacePerso_WAR_EPportlet_:groupTitre',
                   'javax.faces.behavior.event': 'click',
                   'javax.faces.partial.event': 'click',
                   'javax.faces.ViewState': javaxvs2,
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm': '_EspacePerso_WAR_EPportlet_:seConnecterForm',
                   'javax.faces.encodedURL': 'https://monespace.grdf.fr/web/guest/monespace?p_p_id=EspacePerso_WAR_EPportlet&amp;p_p_lifecycle=2&amp;p_p_state=normal&amp;p_p_mode=view&amp;p_p_cacheability=cacheLevelPage&amp;p_p_col_id=column-2&amp;p_p_col_count=1&amp;_EspacePerso_WAR_EPportlet__jsfBridgeAjax=true&amp;_EspacePerso_WAR_EPportlet__facesViewIdResource=%2Fviews%2FespacePerso%2FseconnecterEspaceViewMode.xhtml',
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm:email': username,
                   '_EspacePerso_WAR_EPportlet_:seConnecterForm:passwordSecretSeConnecter': password
        }


        req = session.post(LOGIN_BASE_URI + API_ENDPOINT_LOGIN, data=payload, allow_redirects=False)
        session_cookie = req.cookies.get('GRDF_EP')

        if not 'GRDF_EP' in session.cookies:
            raise GazparLoginException("Login unsuccessful. Check your credentials.")

        return session

    # Date formatting 
    def dtostr(self, date):
        return date.strftime("%d/%m/%Y")

    def get_data_per_hour(self, session, start_date, end_date):
        """Retreives hourly energy consumption data."""
        return self._get_data(session, 'Heure', start_date, end_date)

    def get_data_per_day(self, session, start_date, end_date):
        """Retreives daily energy consumption data."""
        return self._get_data(session, 'Jour', start_date, end_date)

    def get_data_per_week(self, session, start_date, end_date):
        """Retreives weekly energy consumption data."""
        return self._get_data(session, 'Semaine', start_date, end_date)

    def get_data_per_month(self, session, start_date, end_date):
        """Retreives monthly energy consumption data."""
        return self._get_data(session, 'Mois', start_date, end_date)

    def get_data_per_year(self, session):
        """Retreives yearly energy consumption data."""
        return self._get_data(session, 'Mois')

    def _get_data(self, session, resource_id, start_date=None, end_date=None):

        session.headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Mobile Safari/537.36',
                    'Accept-Language':'fr,fr-FR;q=0.8,en;q=0.6',
                    'Accept-Encoding':'gzip, deflate, br', 
                    'Accept':'application/xml, application/json, text/javascript, */*; q=0.01',
                    'Faces-Request':'partial/ajax',
                    'Host': 'monespace.grdf.fr',
                    'Origin':'https://monespace.grdf.fr',
                    'Referer':'https://monespace.grdf.fr/monespace/particulier/consommation/consommation',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                    'X-Requested-With':'XMLHttpRequest'}

        payload = {
                    'javax.faces.partial.ajax':'true',
                    'javax.faces.source':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:j_idt139',
                    'javax.faces.partial.execute':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:j_idt139',
                    'javax.faces.partial.render':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille',
                    'javax.faces.behavior.event':'click',
                    'javax.faces.partial.event':'click',
                    '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille':' _eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille',
                    'javax.faces.encodedURL':'https://monespace.grdf.fr/web/guest/monespace/particulier/consommation/consommations?p_p_id=eConsoconsoDetaille_WAR_eConsoportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-3&p_p_col_count=5&p_p_col_pos=3&_eConsoconsoDetaille_WAR_eConsoportlet__jsfBridgeAjax=true&_eConsoconsoDetaille_WAR_eConsoportlet__facesViewIdResource=%2Fviews%2Fconso%2Fdetaille%2FconsoDetailleViewMode.xhtml',
                   'javax.faces.ViewState': self._javavxs }


        params = {
                   'p_p_id':'eConsosynthese_WAR_eConsoportlet',
                   'p_p_lifecycle':'2',
                   'p_p_state':'normal',
                   'p_p_mode':'view',
                   'p_p_cacheability':'cacheLevelPage',
                   'p_p_col_id':'column-3',
                   'p_p_col_count':'5',
                   'p_p_col_pos':'3',
                   '_eConsosynthese_WAR_eConsoportlet__jsfBridgeAjax':'true',
                   '_eConsosynthese_WAR_eConsoportlet__facesViewIdResource':'/views/compteur/synthese/syntheseViewMode.xhtml' }

        r=session.get('https://monespace.grdf.fr/monespace/particulier/consommation/consommations', allow_redirects=False, verify=False, timeout=None)
        if r.status_code != requests.codes.ok:
            print("status 1e appel:"+r.status_code+'\n');
        parser = etree.HTMLParser()
        tree   = etree.parse(io.StringIO(r.text), parser)
        value=tree.xpath("//div[@id='_eConsoconsoDetaille_WAR_eConsoportlet_']/form[@id='_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille']/input[@id='javax.faces.ViewState']/@value")

        self._javavxs=value

        #Step 1
        payload = {
                   'javax.faces.partial.ajax':'true',
                   'javax.faces.source':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:j_idt139',
                   'javax.faces.partial.execute':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:j_idt139',
                   'javax.faces.partial.render':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille',
                   'javax.faces.behavior.event':'click',
                   'javax.faces.partial.event':'click',
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille',
                   'javax.faces.encodedURL':'https://monespace.grdf.fr/web/guest/monespace/particulier/consommation/consommations?p_p_id=eConsoconsoDetaille_WAR_eConsoportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-3&p_p_col_count=5&p_p_col_pos=3&_eConsoconsoDetaille_WAR_eConsoportlet__jsfBridgeAjax=true&_eConsoconsoDetaille_WAR_eConsoportlet__facesViewIdResource=%2Fviews%2Fconso%2Fdetaille%2FconsoDetailleViewMode.xhtml',
                   'javax.faces.ViewState': self._javavxs
        }

        params = {
                   'p_p_id':'eConsoconsoDetaille_WAR_eConsoportlet',
                   'p_p_lifecycle':'2',
                   'p_p_state':'normal',
                   'p_p_mode':'view',
                   'p_p_cacheability':'cacheLevelPage',
                   'p_p_col_id':'column-3',
                   'p_p_col_count':'5',
                   'p_p_col_pos':'3',
                   '_eConsoconsoDetaille_WAR_eConsoportlet__jsfBridgeAjax':'true',
                   '_eConsoconsoDetaille_WAR_eConsoportlet__facesViewIdResource':'/views/conso/detaille/consoDetailleViewMode.xhtml'
        }

        session.cookies['KPISavedRef'] ='https://monespace.grdf.fr/monespace/particulier/consommation/consommations'

        req = session.post('https://monespace.grdf.fr/monespace/particulier/consommation/consommations', allow_redirects=False, data=payload, params=params)
        if req.status_code != requests.codes.ok:
            print("status 2e appel:"+r.status_code+'\n');


        # We send the session token so that the server knows who we are
        payload = {
                   'javax.faces.partial.ajax':'true',
                   'javax.faces.source':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1:2',
                   'javax.faces.partial.execute':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1',
                   'javax.faces.partial.render':'_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:refreshHighchart _eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:updateDatesBean _eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:boutonTelechargerDonnees _eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite _eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:idBlocSeuilParametrage',
                   'javax.faces.behavior.event': 'valueChange',
                   'javax.faces.partial.event': 'change',
                   'eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille': '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille',
                    'javax.faces.encodedURL': 'https://monespace.grdf.fr/web/guest/monespace/particulier/consommation/consommations?p_p_id=eConsoconsoDetaille_WAR_eConsoportlet&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_cacheability=cacheLevelPage&p_p_col_id=column-3&p_p_col_count=5&p_p_col_pos=3&_eConsoconsoDetaille_WAR_eConsoportlet__jsfBridgeAjax=true&_eConsoconsoDetaille_WAR_eConsoportlet__facesViewIdResource=%2Fviews%2Fconso%2Fdetaille%2FconsoDetailleViewMode.xhtml',
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:idDateDebutConsoDetaille':start_date,
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:idDateFinConsoDetaille':end_date,
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite1':resource_id.lower(),
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:panelTypeGranularite3':'mois',
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:selecteurVolumeType2':'kwh',
                   '_eConsoconsoDetaille_WAR_eConsoportlet_:idFormConsoDetaille:selecteurVolumeType4':'kwh',
                   'javax.faces.ViewState': self._javavxs
        }

        params = {
                   'p_p_id':'eConsoconsoDetaille_WAR_eConsoportlet',
                   'p_p_lifecycle':'2',
                   'p_p_state':'normal',
                   'p_p_mode':'view',
                   'p_p_cacheability':'cacheLevelPage',
                   'p_p_col_id':'column-3',
                   'p_p_col_count':'5',
                   'p_p_col_pos':'3',
                   '_eConsoconsoDetaille_WAR_eConsoportlet__jsfBridgeAjax':'true',
                   '_eConsoconsoDetaille_WAR_eConsoportlet__facesViewIdResource':'/views/conso/detaille/consoDetailleViewMode.xhtml'
        }

        session.cookies['KPISavedRef'] ='https://monespace.grdf.fr/monespace/particulier/consommation/consommations'

        req = session.post('https://monespace.grdf.fr/monespace/particulier/consommation/consommations', allow_redirects=False, data=payload, params=params)
        if req.status_code != requests.codes.ok:
            print("status recup data: "+r.status_code+'\n');
        # Parse to get the data
        md = re.search("donneesCourante = \"(.*?)\"", req.text)
        d = md.group(1)
        mt = re.search("tooltipDatesInfo = \"(.*?)\"", req.text)
        t = mt.group(1)

        # Make json
        now = datetime.datetime.now()

        ts=t.split(",")
        ds=d.split(",")
        size=len(ts)
        data = []
        i=0
        while i<size:
            if ds[i]!="null":
                data.append({'conso':ds[i], 'time':ts[i].replace('Le ','')})
                
            i +=1
        json_data = json.dumps(data)

        #if 300 <= req.status_code < 400:
        #   # So... apparently, we may need to do that once again if we hit a 302
        #   # ¯\_(ツ)_/¯
        #   req = session.post(API_BASE_URI + API_ENDPOINT_DATA, allow_redirects=False, data=payload, params=params)

        if req.status_code == 200 and req.text is not None and "Conditions d'utilisation" in req.text:
            raise GazparLoginException("You need to accept the latest Terms of Use. Please manually log into the website, "
                                      "then come back.")

        try:
            res = data
        except:
            logging.info("Unable to get data")
            raise GazparServiceException("Unable to get data")

        #if res['etat'] and res['etat']['valeur'] == 'erreur' and res['etat']['erreurText']:
        #    raise GazparServiceException(html.unescape(res['etat']['erreurText']))

        return res


class GazparLoginException(Exception):
    """Thrown if an error was encountered while retrieving energy consumption data."""
    pass

class GazparServiceException(Exception):
    """Thrown when the webservice threw an exception."""
    pass


