import json
import random
import re
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

from core.settings import PARSER_USER_AGENTS_LIST

PAGE_URL = 'https://suchen.mobile.de/fahrzeuge/search.html?scopeId=C&name=&email=on&makeModelVariant1.makeId=&makeModelVariant1.modelDescription=&makeModelVariantExclusions%5B0%5D.makeId=&doorCount=&sld=&sfmr=false&minHu=&numberOfPreviousOwners=&cn=&maxConsumptionCombined=&emissionsSticker=&emissionClass=&tct=&spc=&airbag=&climatisation=&adLimitation=&daysAfterCreation=&damageUnrepaired=ALSO_DAMAGE_UNREPAIRED&export=&usedCarSeals=&minPowerAsArray=PS&maxPowerAsArray=PS&lang=en'


def parse_page_alpha(page_url: str):
    response = requests.get(page_url, headers={
        'User-Agent': random.choice(PARSER_USER_AGENTS_LIST)
    })
    try:
        response.raise_for_status()
    except Exception as ex:
        print(response.text)
        raise ex

    # print(response.text)

    soup = BeautifulSoup(response.content, 'lxml')
    container = soup.find('div', 'dsp-form-inputs-container')

    names_dict = {}
    values_dict = defaultdict(lambda: defaultdict(dict))
    for el in container.find_all(re.compile(r'select|input')):
        if el.name == 'select':
            param = el.get('name')
            param_id = el.get('id')
            if param is None and el.name == 'select':
                new_el = el.parent.find('input')
                param = new_el.get('name') or new_el.get('id')

            try:
                label = container.find('label', {"for": param_id}) or el.parent.find(
                    'legend') or el.parent.parent.parent.find('legend')
                param_name = label.text
            except AttributeError:
                param_name = None

            names_dict[param] = param_name
            values_dict['select'][param] = {option.get('value'): option.text for option in el.find_all('option')}
        else:
            param_id = el.get('id')
            param = el.get('name')

            try:
                label = el.parent.parent.find('label', {"for": param_id}) or el.parent.find(
                    'legend')
                param_name = label.text
            except AttributeError:
                param_name = None

            names_dict[param] = param_name
            values_dict[el.get('type')][param].update({el.get('value'): param_name})

    with open('names.json', 'w') as names_f, open('values.json', 'w') as values_f:
        json.dump(names_dict, names_f, ensure_ascii=False)
        json.dump(values_dict, values_f, ensure_ascii=False)


def parse_page_beta(page_url: str):
    response = requests.get(page_url, headers={
        'User-Agent': random.choice(PARSER_USER_AGENTS_LIST)
    })
    try:
        response.raise_for_status()
    except Exception as ex:
        print(response.text)
        raise ex

    soup = BeautifulSoup(response.content, 'lxml')
    container = soup.find('div', 'dsp-form-inputs-container').find('div')

    names_dict = {}
    values_dict = defaultdict(lambda: defaultdict(dict))
    for el in container.find_all(re.compile(r'select|input')):
        if el.name == 'select':
            param = el.get('name')
            param_id = el.get('id')
            if param is None and el.name == 'select':
                new_el = el.parent.find('input')
                param = new_el.get('name') or new_el.get('id')

            try:
                tmp = el
                while getattr(tmp, 'name') not in ['fieldset', 'html']:
                    tmp = tmp.parent
                if tmp.name == 'fieldset':
                    param_name = tmp.find('legend').text
                else:
                    label = el.parent.find('label', {"for": param_id})
                    param_name = label.text
            except AttributeError:
                param_name = None

            names_dict[param] = param_name
            values_dict['select'][param] = {option.get('value'): option.text for option in el.find_all('option')}
        else:
            param_id = el.get('id')
            param = el.get('name')

            try:
                tmp = el
                while getattr(tmp, 'name') not in ['fieldset', 'html']:
                    tmp = tmp.parent
                if tmp.name == 'fieldset':
                    param_name = tmp.find('legend').text
                else:
                    label = el.parent.find('label', {"for": param_id})
                    param_name = label.text
            except AttributeError:
                param_name = None

            names_dict[param] = param_name
            values_dict[el.get('type')][param].update({el.get('value'): param_name})

    with open('names.json', 'w') as names_f, open('values.json', 'w') as values_f:
        json.dump(names_dict, names_f, ensure_ascii=False)
        json.dump(values_dict, values_f, ensure_ascii=False)


if __name__ == '__main__':
    parse_page_beta(PAGE_URL)
