import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error

def lambda_handler(event, context):
    """Fetch and parse IMS sea forecast XML data"""
    try:
        # Fetch live XML data from IMS
        url = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_sea.xml"
        
        try:
            print(f"Fetching XML from: {url}")
            with urllib.request.urlopen(url, timeout=10) as response:
                raw_data = response.read()
                # Try different encodings
                for encoding in ['utf-8', 'iso-8859-1', 'windows-1255']:
                    try:
                        xml_data = raw_data.decode(encoding)
                        print(f"Successfully decoded with {encoding}, length: {len(xml_data)}")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    xml_data = raw_data.decode('utf-8', errors='ignore')
                    print(f"Decoded with errors ignored, length: {len(xml_data)}")
        except (urllib.error.URLError, UnicodeDecodeError) as e:
            print(f"Failed to fetch/decode XML: {e}, using fallback data")
            # Fallback to static data if URL fails
            xml_data = """<IsraelSeaForecastMorning>
<Originator>
<Organization>Israel Meteorological Service</Organization>
<Generator>Global Distribution of Meteorological Information</Generator>
</Originator>
<Identification>
<Title>Israel Sea Forecast (Morning)</Title>
<IssueDateTime>2025-09-17 00:03</IssueDateTime>
</Identification>
<Location>
<LocationMetaData>
<LocationId>213</LocationId>
<LocationNameEng>Southern Coast</LocationNameEng>
<LocationNameHeb>החוף הדרומי</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>30</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>210</LocationId>
<LocationNameEng>Central Coast</LocationNameEng>
<LocationNameHeb>החוף המרכזי</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>30</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>212</LocationId>
<LocationNameEng>Northern Coast</LocationNameEng>
<LocationNameHeb>החוף הצפוני</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>50 / 50-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>29</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-25</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>211</LocationId>
<LocationNameEng>Sea of Galilee</LocationNameEng>
<LocationNameHeb>כנרת</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>40 / 30-80</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>29</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>225-315/10-35</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
<Location>
<LocationMetaData>
<LocationId>214</LocationId>
<LocationNameEng>Gulf of Eilat</LocationNameEng>
<LocationNameHeb>מפרץ אילת</LocationNameHeb>
</LocationMetaData>
<LocationData>
<TimeUnitData>
<DateTimeFrom>2025-09-17 08:00</DateTimeFrom>
<DateTimeTo>2025-09-17 20:00</DateTimeTo>
<Element>
<ElementName>Sea status and waves height</ElementName>
<ElementValue>30 / 20-40</ElementValue>
</Element>
<Element>
<ElementName>Sea temperature</ElementName>
<ElementValue>27</ElementValue>
</Element>
<Element>
<ElementName>Wind direction and speed</ElementName>
<ElementValue>360-045/15-30</ElementValue>
</Element>
</TimeUnitData>
</LocationData>
</Location>
</IsraelSeaForecastMorning>"""
        
        print("Parsing XML data...")
        root = ET.fromstring(xml_data)
        
        forecast_data = {
            "metadata": {
                "organization": root.find('.//Organization').text,
                "title": root.find('.//Title').text,
                "issue_datetime": root.find('.//IssueDateTime').text
            },
            "locations": []
        }
        print(f"Parsed metadata: {forecast_data['metadata']}")
        
        for location in root.findall('Location'):
            location_meta = location.find('LocationMetaData')
            location_data = location.find('LocationData')
            
            # Map location names to handle IMS naming inconsistencies
            original_name = location_meta.find('LocationNameEng').text
            mapped_name = map_location_name(original_name)
            
            location_info = {
                "id": location_meta.find('LocationId').text,
                "name_eng": mapped_name,
                "name_heb": location_meta.find('LocationNameHeb').text,
                "coordinates": get_location_coordinates(mapped_name),
                "forecasts": []
            }
            
            for time_unit in location_data.findall('TimeUnitData'):
                forecast_period = {
                    "from": time_unit.find('DateTimeFrom').text,
                    "to": time_unit.find('DateTimeTo').text,
                    "elements": {}
                }
                
                for element in time_unit.findall('Element'):
                    element_name = element.find('ElementName').text
                    element_value = element.find('ElementValue').text
                    
                    if element_name == "Sea status and waves height":
                        forecast_period["elements"]["wave_height"] = element_value
                    elif element_name == "Sea temperature":
                        forecast_period["elements"]["sea_temperature"] = int(element_value)
                    elif element_name == "Wind direction and speed":
                        forecast_period["elements"]["wind"] = element_value
                
                location_info["forecasts"].append(forecast_period)
            
            forecast_data["locations"].append(location_info)
        
        print(f"Processed {len(forecast_data['locations'])} locations")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(forecast_data)
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }

def map_location_name(original_name):
    """Map IMS location names to our preferred names"""
    name_mapping = {
        "Gulf of Elat": "Gulf of Eilat"
    }
    return name_mapping.get(original_name, original_name)

def get_location_coordinates(location_name):
    """Get coordinates for location names"""
    # Input validation - sanitize location name
    if not isinstance(location_name, str):
        return {"lat": 0, "lng": 0}
    
    location_name = location_name.strip()
    
    coordinates = {
        "Northern Coast": {"lat": 32.8, "lng": 35.0},
        "Central Coast": {"lat": 32.0, "lng": 34.8},
        "Southern Coast": {"lat": 31.4, "lng": 34.3},
        "Sea of Galilee": {"lat": 32.8, "lng": 35.6},
        "Gulf of Eilat": {"lat": 29.5, "lng": 34.9}
    }
    
    return coordinates.get(location_name, {"lat": 32.0, "lng": 34.8})