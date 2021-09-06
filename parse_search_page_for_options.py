import json
import random
import re
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select

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
                param_name = getattr(el.parent.find('label', {"for": param_id}), 'text', None)
                if param_name is None:
                    tmp = el
                    while getattr(tmp, 'name') not in ['fieldset', 'html']:
                        tmp = tmp.parent
                    if tmp.name == 'fieldset':
                        param_name = tmp.find('legend').text
            except AttributeError:
                param_name = None

            names_dict.setdefault(param, param_name)
            values_dict['select'][param] = {option.get('value'): option.text for option in el.find_all('option')}
        else:
            param_id = el.get('id')
            param = el.get('name')

            try:
                tmp = el
                while getattr(tmp, 'name') not in ['fieldset', 'html'] and 'content-row' not in (
                        tmp.get('class') or []):
                    tmp = tmp.parent
                if tmp.name != 'html':
                    param_name = tmp.find(re.compile('legend|label')).text
                    names_dict.setdefault(param, param_name)

                param_name = getattr(el.parent.find('label', {"for": param_id}), 'text')

            except AttributeError:
                param_name = None

            names_dict.setdefault(param, param_name)
            values_dict[el.get('type')][param].update({el.get('value'): param_name})

    with open('names.json', 'w') as names_f, open('values.json', 'w') as values_f:
        json.dump(names_dict, names_f, ensure_ascii=False)
        json.dump(values_dict, values_f, ensure_ascii=False)


def parse_make_model(page_url: str):
    with webdriver.Chrome() as driver:
        driver.get(page_url)
        make_select = Select(driver.find_element_by_id('selectMake1-ds'))
        makes = []
        for option_index, make in enumerate(make_select.options):
            make_select.select_by_index(option_index)
            if make.text.lower() == 'any':
                continue
            time.sleep(0.2)
            model_select = Select(driver.find_element_by_id('selectModel1-ds'))
            makes.append(
                {
                    'id': make.get_attribute('value'),
                    'name': make.text,
                    'models': [
                        {
                            'id': model.get_attribute('value'),
                            'name': model.text
                        }
                        for model in model_select.options
                        if model.text.lower() != 'any'
                    ]
                }
            )

    with open('makes_models.json', 'w') as f:
        json.dump(makes, f, ensure_ascii=False)


def select_all_options_and_get_link(page_url: str) -> str:
    with webdriver.Chrome() as driver:
        actions = ActionChains(driver)
        driver.get(page_url)

        inputs = driver.find_elements_by_tag_name('input')
        for input_ in filter(lambda x: x.get_attribute('type') in ['text', 'checkbox', 'radio'], inputs):
            if input_.tag_name not in ['text', 'checkbox', 'radio']:
                continue
            try:
                actions.move_to_element(input_).perform()
                input_.click()
                time.sleep(0.3)
            except Exception as e:
                print('input', input_.get_attribute('id'))
                raise

        selects = driver.find_elements_by_tag_name('select')
        for select in selects:
            try:
                actions.move_to_element(select).perform()
                s = Select(select)
                s.select_by_index(1)
                time.sleep(0.3)
            except Exception as e:
                print('select', select.get_attribute('id'))
                raise

        submit_button = driver.find_element_by_id('dsp-upper-search-btn')
        submit_button.click()

        time.sleep(3)

        return driver.current_url


if __name__ == '__main__':
    # parse_page_beta(PAGE_URL)
    # parse_make_model(PAGE_URL)
    select_all_options_and_get_link(PAGE_URL)

TMP_TEST_URL_WITH_ALL_PARAMS = 'https://suchen.mobile.de/fahrzeuge/search.html?ab=FRONT_AND_SIDE_AND_MORE_AIRBAGS&ao=PICTURES&ao=QUALITY_SEAL&c=Cabrio&c=EstateCar&c=Limousine&c=OffRoad&c=OtherCar&c=SmallCar&c=SportsCar&c=Van&cc=1000%3A9000&clim=MANUAL_CLIMATISATION&cn=DE&cnc=%3A15&dam=0&doc=14&door=FOUR_OR_FIVE&ecol=BEIGE&ecol=BLACK&ecol=BLUE&ecol=BROWN&ecol=GOLD&ecol=GREEN&ecol=GREY&ecol=ORANGE&ecol=PURPLE&ecol=RED&ecol=SILVER&ecol=WHITE&ecol=YELLOW&ems=EMISSIONSSTICKER_GREEN&fe=ABS&fe=ELECTRIC_HEATED_SEATS&fe=FULL_SERVICE_HISTORY&fe=HEAD_UP_DISPLAY&fe=ISOFIX&fe=LANE_DEPARTURE_WARNING&fe=METALLIC&fe=NONSMOKER_VEHICLE&fe=PARTICULATE_FILTER_DIESEL&fr=1900%3A2021&ft=CNG&ft=DIESEL&ft=ELECTRICITY&ft=ETHANOL&ft=HYBRID&ft=HYBRID_DIESEL&ft=HYDROGENIUM&ft=LPG&ft=OTHER&ft=PETROL&gi=18&icol=BEIGE&icol=BLACK&icol=BROWN&icol=GREY&icol=OTHER_INTERIOR_COLOR&isSearchRequest=true&it=ALCANTARA&it=FABRIC&it=LEATHER&it=OTHER_INTERIOR_TYPE&it=PARTIAL_LEATHER&it=VELOUR&ml=5000%3A200000&ms=140%3B%3B%3B%3B&ms=25200%3B14%3B%3BVariant%3B&ms%21=140%3B10%3B%3B%3B&p=500%3A90000&pa=AUTOMATIC_PARKING&pa=CAM_360_DEGREES&pa=FRONT_SENSORS&pa=REAR_SENSORS&pa=REAR_VIEW_CAM&pvo=4&pw=25%3A333&rtd=1&s=Car&sc=2%3A9&sfmr=false&spc=CRUISE_CONTROL&sr=3&st=DEALER&subc=CLASSIC&subc=DEMONSTRATION&subc=EMPLOYEES_CAR&subc=PRE_REGISTRATION&tct=TRAILER_COUPLING_FIX&tr=AUTOMATIC_GEAR&tr=MANUAL_GEAR&tr=SEMIAUTOMATIC_GEAR&ucs=Any&vc=Car'
TMP_TEST_URL_WITH_ALL_PARAMS_WITH_SORTING = 'https://suchen.mobile.de/fahrzeuge/search.html?adLimitation=ONLY_DEALER_ADS&airbag=FRONT_AND_SIDE_AND_MORE_AIRBAGS&categories=Cabrio&categories=EstateCar&categories=Limousine&categories=OffRoad&categories=OtherCar&categories=SmallCar&categories=SportsCar&categories=Van&climatisation=MANUAL_OR_AUTOMATIC_CLIMATISATION&cn=DE&colors=BEIGE&colors=BLACK&colors=BLUE&colors=BROWN&colors=GOLD&colors=GREEN&colors=GREY&colors=ORANGE&colors=PURPLE&colors=RED&colors=SILVER&colors=WHITE&colors=YELLOW&damageUnrepaired=NO_DAMAGE_UNREPAIRED&daysAfterCreation=14&doorCount=FOUR_OR_FIVE&emissionsSticker=EMISSIONSSTICKER_GREEN&features=ABS&features=ELECTRIC_HEATED_SEATS&features=FULL_SERVICE_HISTORY&features=HEAD_UP_DISPLAY&features=ISOFIX&features=LANE_DEPARTURE_WARNING&features=METALLIC&features=NONSMOKER_VEHICLE&features=PARTICULATE_FILTER_DIESEL&fuels=CNG&fuels=DIESEL&fuels=ELECTRICITY&fuels=ETHANOL&fuels=HYBRID&fuels=HYBRID_DIESEL&fuels=HYDROGENIUM&fuels=LPG&fuels=OTHER&fuels=PETROL&grossPrice=true&interiorColors=BEIGE&interiorColors=BLACK&interiorColors=BROWN&interiorColors=GREY&interiorColors=OTHER_INTERIOR_COLOR&interiorTypes=ALCANTARA&interiorTypes=FABRIC&interiorTypes=LEATHER&interiorTypes=OTHER_INTERIOR_TYPE&interiorTypes=PARTIAL_LEATHER&interiorTypes=VELOUR&isSearchRequest=true&makeModelVariant1.makeId=140&makeModelVariant2.makeId=25200&makeModelVariant2.modelDescription=Variant&makeModelVariant2.modelId=14&makeModelVariantExclusions%5B0%5D.makeId=140&makeModelVariantExclusions%5B0%5D.modelId=10&maxConsumptionCombined=15&maxCubicCapacity=9000&maxFirstRegistrationDate=2021-12-31&maxMileage=200000&maxPowerAsArray=333&maxPowerAsArray=KW&maxPrice=90000&maxSeats=9&minCubicCapacity=1000&minFirstRegistrationDate=1900-01-01&minHu=18&minMileage=5000&minPowerAsArray=25&minPowerAsArray=KW&minPrice=500&minSeats=2&numberOfPreviousOwners=4&parkAssistents=AUTOMATIC_PARKING&parkAssistents=CAM_360_DEGREES&parkAssistents=FRONT_SENSORS&parkAssistents=REAR_SENSORS&parkAssistents=REAR_VIEW_CAM&readyToDrive=ONLY_READY_TO_DRIVE&scopeId=C&sfmr=false&sortOption.sortBy=searchNetGrossPrice&sortOption.sortOrder=ASCENDING&spc=CRUISE_CONTROL&sr=3&tct=TRAILER_COUPLING_FIX&transmissions=AUTOMATIC_GEAR&transmissions=MANUAL_GEAR&transmissions=SEMIAUTOMATIC_GEAR&usageType=CLASSIC&usageType=DEMONSTRATION&usageType=EMPLOYEES_CAR&usageType=PRE_REGISTRATION&usedCarSeals=Any&withImage=true'