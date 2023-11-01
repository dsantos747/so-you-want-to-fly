from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
from requests import get, post
import json
from geopy.distance import geodesic
from datetime import datetime
import copy


def normalise_date(ugly_date):
    return datetime.strptime(ugly_date, "%Y-%m-%d").strftime("%d/%m/%Y")


def get_airport_list(latitude, longitude, max_radius, min_radius=0):
    def distance_calculator(item):
        ## item[0] = IATA code, item[1] = latitude, item[2] = longitude
        distance = geodesic((latitude, longitude), (item[1], item[2])).kilometers
        return item[0] if min_radius <= distance <= max_radius else None

    result = ",".join(filter(None, map(distance_calculator, full_airports_list)))
    # FIX: the tequila API has a "URI limit". So maybe stop adding destinations to the list after a certain point (we don't need ALL the medium-sized airports)

    return result


def tequila_query(
    flight_origin,
    flight_destination,
    outbound_date,
    return_date,
    outbound_date_end_range=None,
    return_date_end_range=None,
    price_limit=None,
):
    if outbound_date_end_range == None:
        outbound_date_end_range = outbound_date
    if return_date_end_range == None:
        return_date_end_range = return_date

    url = f"https://api.tequila.kiwi.com/v2/search"
    headers = {"Content-Type": "application/json", "apikey": TEQUILA_KEY}
    params = {
        "fly_from": flight_origin,
        "fly_to": flight_destination,
        "date_from": outbound_date,
        "date_to": outbound_date_end_range,
        "return_from": return_date,
        "return_to": return_date_end_range,
        #  "max_fly_duration": "DUMMY",
        #  "price_to": price_limit, #might be useful to control the results a bit.
        "curr": "EUR",
        "sort": "quality",  # quality or price(default)
        "limit": 500,  # max 1000
    }

    result = get(url, headers=headers, params=params)
    if result.status_code != 200:
        print(f"Tequila response is {result}")
        print(result.text)
        # throw error here
    else:
        return result.json()


def tequila_parse(tequila_dict):
    parsed_dict = {}
    for route in tequila_dict["data"]:
        if route["cityTo"] not in parsed_dict:
            parsed_dict[route["cityTo"]] = {}
        if len(parsed_dict[route["cityTo"]]) < 5:
            flights_arr = [{}, {}]
            count_out = 0
            count_ret = 0
            for leg in route["route"]:
                leg_object = {
                    "id": leg["id"],
                    "combination_id": leg["combination_id"],
                    "flyFrom": leg["flyFrom"],
                    "cityFrom": leg["cityFrom"],
                    "flyTo": leg["flyTo"],
                    "cityTo": leg["cityTo"],
                    "local_departure": leg["local_departure"],
                    "utc_departure": leg["utc_departure"],
                    "local_arrival": leg["local_arrival"],
                    "utc_arrival": leg["utc_arrival"],
                    "airline": leg["airline"],
                    "flight_no": leg["flight_no"],
                    "operating_carrier": leg["operating_carrier"],
                    "operating_flight_no": leg["operating_flight_no"],
                    "return": leg["return"],
                }
                if leg["return"] == 0:
                    count_out += 1
                    flights_arr[0][f"step_{count_out}"] = leg_object
                else:
                    count_ret += 1
                    flights_arr[1][f"step_{count_ret}"] = leg_object

            route_object = {
                "id": route["id"],
                "flyFrom": route["flyFrom"],
                "cityFrom": route["cityFrom"],
                "flyTo": route["flyTo"],
                "cityTo": route["cityTo"],
                "countryFrom": route["countryFrom"]["name"],
                "countryTo": route["countryTo"]["name"],
                "local_departure": route["local_departure"],
                "utc_departure": route["utc_departure"],
                "local_arrival": route["local_arrival"],
                "utc_arrival": route["utc_arrival"],
                "nightsInDest": route["nightsInDest"],
                "quality": route["quality"],
                "distance": route["distance"],
                "duration": {
                    "departure": route["duration"]["departure"],
                    "return": route["duration"]["return"],
                    "total": route["duration"]["total"],
                },
                "price": route["price"],
                "airlines": route["airlines"],
                "flights": flights_arr,
                "total_legs": count_out + count_ret,
                "out_legs": count_out,
                "return_legs": count_ret,
                "booking_token": route["booking_token"],
                "deep_link": route["deep_link"],
                "img_url": unsplash_fetch(route["cityTo"])
                # "img_url": unsplash_fetch(f"{route['cityTo']}, {route['countryTo']['name']}")
                if parsed_dict[route["cityTo"]] == {}
                else parsed_dict[route["cityTo"]]["option_1"]["img_url"],
            }

            # parsed_dict[route["cityTo"]].append(route_object)
            parsed_dict[route["cityTo"]][
                f"option_{(len(parsed_dict[route['cityTo']]) + 1)}"
            ] = route_object

    return parsed_dict


def emissions_flights_list(flights_dict):
    flights_list = []
    for destination in flights_dict:
        for option in flights_dict[destination]:
            for flight in flights_dict[destination][option]["flights"][0]:
                flights_list.append(
                    tim_params_builder(
                        flights_dict[destination][option]["flights"][0][flight]
                    )
                )
            for flight in flights_dict[destination][option]["flights"][1]:
                flights_list.append(
                    tim_params_builder(
                        flights_dict[destination][option]["flights"][1][flight]
                    )
                )

    return {"flights": flights_list}


def tim_params_builder(flight_object):
    return {
        "origin": flight_object["flyFrom"],
        "destination": flight_object["flyTo"],
        "operatingCarrierCode": flight_object["operating_carrier"]
        if flight_object["operating_carrier"] != ""
        else flight_object["airline"],
        "flightNumber": int(flight_object["operating_flight_no"])
        if flight_object["operating_flight_no"] != ""
        else int(flight_object["flight_no"]),
        "departureDate": {
            "year": flight_object["local_departure"][:4],
            "month": flight_object["local_departure"][5:7],
            "day": flight_object["local_departure"][8:10],
        },
    }


def emissions_fetch(flights_object, flight_class="economy"):
    url = f"https://travelimpactmodel.googleapis.com/v1/flights:computeFlightEmissions?key={TIM_KEY}"
    headers = {"Content-Type": "application/json"}
    params_json = json.dumps(flights_object)

    result = post(url, headers=headers, data=params_json)
    result_json = result.json()

    emissions_results = []
    for flight in result_json["flightEmissions"]:
        emissions_results.append(
            0
            if flight.get("emissionsGramsPerPax") == None
            else flight["emissionsGramsPerPax"][flight_class]
        )

    return emissions_results


def emissions_parse(flights_dict, emissions_results):
    new_flights_dict = copy.deepcopy(flights_dict)
    for destination in flights_dict:
        for option in flights_dict[destination]:
            outbound_emissions = 0
            remove_option = False
            for outbound_flight in flights_dict[destination][option]["flights"][0]:
                emissions = emissions_results.pop(0)
                if emissions == 0:
                    # print(
                    #     f"no emissions data for flight to {flights_dict[destination][option]['flights'][0][outbound_flight]['flyTo']}"
                    # )
                    remove_option = True
                    break
                else:
                    new_flights_dict[destination][option]["flights"][0][
                        outbound_flight
                    ]["flight_emissions"] = emissions
                outbound_emissions += emissions

            if remove_option:
                del new_flights_dict[destination][option]
                # print(f"removed trip to {destination}")
                continue

            return_emissions = 0
            for return_flight in flights_dict[destination][option]["flights"][1]:
                emissions = emissions_results.pop(0)
                if emissions == 0:
                    # print(
                    #     f"no emissions data for flight to {flights_dict[destination][option]['flights'][1][return_flight]['flyTo']}"
                    # )
                    remove_option = True
                    break
                else:
                    new_flights_dict[destination][option]["flights"][1][return_flight][
                        "flight_emissions"
                    ] = emissions
                return_emissions += emissions

            if remove_option:
                del new_flights_dict[destination][option]
                # print(f"removed trip to {destination}")
                continue

            total_emissions = outbound_emissions + return_emissions
            new_flights_dict[destination][option]["trip_emissions"] = total_emissions

        # If destination array is now empty, delete it too (sad)
        if not new_flights_dict[destination]:
            # print(f"removed {destination} as a destination")
            del new_flights_dict[destination]

    return reset_option_numbers(new_flights_dict)


# Can refactor this for sure, probably incorporate this methodology into emissions_parse
def reset_option_numbers(dict):
    output_dict = {}

    for destination, options in dict.items():
        new_options = {}
        count = 1

        for option_key, option_value in options.items():
            new_option_key = f"option_{count}"
            new_options[new_option_key] = option_value
            count += 1

        output_dict[destination] = new_options

    return output_dict


def results_sort(results):
    sorted_results = dict(
        sorted(
            results.items(),
            key=lambda item: min(
                option.get("trip_emissions", float("inf"))
                for option in item[1].values()
            ),
        )
    )
    return sorted_results


def unsplash_fetch(query):
    url = f"https://api.unsplash.com/search/photos/"
    headers = {
        "Content-Type": "application/json",
        "Accept-Version": "v1",
        "Authorization": f"Client-ID {UNSPLASH_ACCESS}",
    }
    params = {"query": query, "orientation": "portrait", "per_page": 1}

    result = get(url, headers=headers, params=params).json()
    img_url = result["results"][0]["urls"]["raw"]
    img_url_resized = img_url + "&w=400&h=600&fit=crop&crop=top,bottom,left,right"
    return img_url_resized


# Get API key from environment variables
env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
load_dotenv(dotenv_path=env_path)
FLASK_ENV = os.getenv("FLASK_ENV")
TIM_KEY = os.getenv("TIM_API_KEY")
TEQUILA_KEY = os.getenv("TEQUILA_API_KEY")
# RAPID_API_KEY = os.getenv("RAPID_API_KEY")
UNSPLASH_ACCESS = os.getenv("UNSPLASH_ACCESS_KEY")
UNSPLASH_SECRET_KEY = os.getenv("UNSPLASH_SECRET_KEY")

current_dir = os.path.dirname(os.path.realpath(__file__))

# Load all airports
with open(os.path.join(current_dir, "data", "airports.json"), "r") as json_file:
    full_airports_list = json.load(json_file)

# App instance
app = Flask(__name__)
CORS(app)

##### TEST - Dummy variables section
# user_location = (38.7813, -9.13592)
# radius_range = [4000, 1500]

##### TEST airport list fetching
# origin_airports = get_airport_list(*user_location, 100) # List of airports in a 100km radius from user's location ### FIX: Change this to a single value?
# destination_airports = get_airport_list(*user_location, search_radius)


##### TEST read data from tequila response, filter and create flights list for emissions testing
# with open(
#     os.path.join(current_dir, "data", "test_tequila_response.json"),
#     "r",
#     encoding="utf-8",
# ) as file:
#     json_data = json.load(file)

# processed_data = tequila_parse(json_data)

# with open(
#     os.path.join(current_dir, "data", "processed_tequila_data.json"), "w"
# ) as file:
#     json.dump(processed_data, file, indent=2)

# tim_processed_data = emissions_flights_list(processed_data)

# with open(os.path.join(current_dir, "data", "prepped_TIM_list.json"), 'w') as file:
#     json.dump(tim_processed_data, file, indent=2)

##### TEST emissions checking

# emissions_results = emissions_fetch(tim_processed_data)

# with open(os.path.join(current_dir, "data", "emissions_results_list.json"), 'w') as file:
#     json.dump(emissions_results, file, indent=2)

##### TEST emissions parsing

# processed_data_with_emissions = emissions_parse(processed_data, emissions_results)

# with open(
#     os.path.join(current_dir, "data", "processed_data_with_emissions.json"), "w"
# ) as file:
#     json.dump(processed_data_with_emissions, file, indent=2)

#### TEST Unsplash API Call
# unsplash_fetch("London") # CALL THIS WHEN BUILDING ROUTE OBJECT

##### TEST individual manual emissions check
# test_flight = {
#     "flights": [
#         {
#         "origin": "PMI",
#         "destination": "BCN",
#         "operatingCarrierCode": "FR",
#         "flightNumber": 3071,
#         "departureDate": {
#           "year": "2024",
#           "month": "04",
#           "day": "03"
#         }
#       }
#     ]
# }
# print(emissions_fetch(test_flight))


##### TEST tequila API call
# origin_airports = get_airport_list(*user_location, 100)
# destination_airports = get_airport_list(*user_location, *radius_range)
# outboundDate = "01/11/2023"
# returnDate = "10/11/2023"
# outboundDateEndRange = "03/11/2023"
# returnDateEndRange = "12/11/2023"
# tequila_result = tequila_query(origin_airports, destination_airports, outboundDate, returnDate, outboundDateEndRange, returnDateEndRange)
# processed_data = tequila_parse(tequila_result)
# print(processed_data)


# App route to return simple JSON message
@app.route("/api/ping", methods=["GET"])
def ping():
    return "I am awake!"


# App route to run request to Travel Impact Model API
@app.route("/api/emissions", methods=["GET"])
def emissions_route():
    print("flask 1")
    user_location = [float(request.args.get("lat")), float(request.args.get("long"))]
    trip_length = request.args.get("len")
    radius_range = (
        [1500, 0]
        if trip_length == "trip-short"
        else [4000, 1500]
        if trip_length == "trip-medium"
        else [15000, 4000]
    )
    outboundDate = normalise_date(request.args.get("out"))
    outboundDateEndRange = normalise_date(request.args.get("outEnd"))
    returnDate = normalise_date(request.args.get("ret"))
    returnDateEndRange = normalise_date(request.args.get("retEnd"))

    origin_airports = get_airport_list(*user_location, 100)
    print("flask 2")
    destination_airports = get_airport_list(*user_location, *radius_range)
    print("flask 3")

    # COMMENT OUT THESE LINES TO AVOID TEQUILA API CALLS DURING DEVELOPMENT
    tequila_result = tequila_query(
        origin_airports,
        destination_airports,
        outboundDate,
        returnDate,
        outboundDateEndRange,
        returnDateEndRange,
    )
    print("flask 4")
    processed_data = tequila_parse(tequila_result)
    print("flask 5")

    # USE THIS INSTEAD TO AVOID TEQUILA API CALLS
    # processed_data = tequila_parse(json_data)

    tim_processed_data = emissions_flights_list(processed_data)
    print("flask 6")
    emissions_results = emissions_fetch(tim_processed_data)
    print("flask 7")
    processed_data_with_emissions = emissions_parse(processed_data, emissions_results)
    print("flask 8")
    sorted_result = results_sort(processed_data_with_emissions)
    print("flask 9")
    print(sorted_result)
    print(jsonify(sorted_result))
    return jsonify(sorted_result)


# Initialise app
if __name__ == "__main__":
    if FLASK_ENV == "production":
        app.run()
    else:
        app.run(debug=True, port=8080)