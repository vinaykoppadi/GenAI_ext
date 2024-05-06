from django.shortcuts import render, redirect
from .models import User, DocumentTypes
from django.http import JsonResponse, HttpResponse
from .tests import (
    input_image_setup,
    get_gemini_response,
    extract_pdf_text,
    dymanic_path,
    delete_all_files,
)
from django.views.decorators.csrf import csrf_exempt
import json
from PIL import Image
import os
from django.db import connection
import random

# Create your views here.


def loginUser(request):

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        try:
            user = User.objects.get(uname=username)
            print(user, user.password)
            if user is not None and user.password == password:
                request.session["username"] = username

                return redirect("upload")
        except Exception as e:
            print(str(e))
            print("User does not exist")

    return render(request, "login.html")


def uploadFile(request):
    username = request.session.get("username", None)
    print(delete_all_files(dymanic_path("staticfiles")))
    delete_all_files(dymanic_path("static", "images"))
    delete_all_files(dymanic_path("static"))
    processed = False
    if request.method == "POST" and request.FILES["file"]:
        uploaded_file = request.FILES["file"]
        print("vinay---filename---", uploaded_file.name)
        if uploaded_file.name.endswith(".pdf"):
            ocr_content = extract_pdf_text(uploaded_file.read())
            image_data = None
            processed = True
            with open(dymanic_path("staticfiles", "ocr_extracted.txt"), "w") as f:
                f.write(ocr_content)

        else:
            image_data = input_image_setup(uploaded_file)
            img = Image.open(uploaded_file)
            img.save(
                dymanic_path("static", "images", f"_{1}.jpeg"), "JPEG", quality=100
            )
            ocr_content = None
            processed = True
        file_name = uploaded_file.name.split(".")[0].capitalize()

        # try:

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT *  FROM  document_extr_documenttypes WHERE DocumentType='{file_name}'"
            )
            columns = [col[0] for col in cursor.description][1:]
            results = cursor.fetchall()[0][1:]
            promt_json = {}
            for row, value in zip(columns, results):
                if value != None:
                    promt_json[row] = value
                    promt_json[row + "Confidence"] = round(random.uniform(0.95, 1), 2)

        # print(promt_json)
        # except:
        #     print("doctype is not founded")

        response = get_gemini_response(
            image_data=image_data,
            ocr_content=ocr_content,
            promt_json=promt_json,
        )
        # print("response.text", response)
        with open(dymanic_path("staticfiles", "genai_extracted.json"), "w") as f:
            json.dump(response, f)

        return render(
            request,
            "index.html",
            {
                "username": username,
                "processed": processed,
                "file_name": uploaded_file.name,
            },
        )
    return render(
        request,
        "index.html",
        {
            "username": username,
        },
    )


def get_fields_data():
    with open(dymanic_path("staticfiles", "genai_extracted.json"), "r") as f:
        data = f.read()
        try:

            input_data = json.loads(
                data.replace('"', "")
                .replace("'", '"')
                .replace("Not found in the document", "")
            )
        except:
            input_data = json.loads(
                data.replace("\\n", "")
                .replace("JSON", "")
                .replace("```", "")
                .replace("\\", "")
                .replace("json", "")
                .replace("Not found in the document", "")[1:-1]
            )

        print(input_data)

    field_values_dict = {}

    for key in input_data:
        if key.endswith("Confidence"):
            continue
        confidence_key = f"{key}Confidence"
        if confidence_key in input_data:
            field_values_dict[key] = [
                input_data[key],
                round(float(input_data[confidence_key]) * 100),
            ]
        else:
            field_values_dict[key] = [input_data[key]]

    print(field_values_dict)

    return field_values_dict


def keyingscreen_view(request):

    change = request.GET.get("Process")

    if change == "True":

        selected_process = request.GET.get("selectedProcess")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT *  FROM  document_extr_documenttypes WHERE DocumentType='{selected_process}'"
            )
            columns = [col[0] for col in cursor.description][1:]
            results = cursor.fetchall()[0][1:]
            promt_json2 = {}
            for row, value in zip(columns, results):
                if value != None:
                    promt_json2[row] = value
                    promt_json2[row + "Confidence"] = round(random.uniform(0.95, 1), 2)

        # print("keyingscreen2", promt_json2)

        with open(dymanic_path("staticfiles", "ocr_extracted.txt"), "r") as f:
            ocr_content = f.read()

        response = get_gemini_response(
            image_data=None,
            ocr_content=ocr_content,
            promt_json=promt_json2,
        )
        print("response.text22", response)
        with open(dymanic_path("staticfiles", "genai_extracted.json"), "w") as f:
            json.dump(response, f)

    field_dict = get_fields_data()
    image_urls = os.listdir(dymanic_path("static", "images"))
    print("image_urls", image_urls)
    file_name = request.GET.get("file_name")
    print("image_urls", file_name)
    classifiction = field_dict["DocumentType"][0]
    return render(
        request,
        "keyingscreen.html",
        {
            "field_values_dict": field_dict,
            "image_urls": image_urls,
            "file_name": file_name,
            "classifiction": classifiction,
        },
    )


@csrf_exempt
def save_data(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            filename = (
                data.get("filename", "default_filename.json").split(".")[0] + ".json"
            )
            form_data = data.get("formData", {})

            # Save the data to a JSON file
            print("vinay----------", filename)
            with open(dymanic_path("static", filename), "w") as json_file:
                json.dump(form_data, json_file)

            return JsonResponse({"status": "success"})

        except json.JSONDecodeError as e:
            return JsonResponse({"status": "success"})

    return JsonResponse({"status": "success"})


def download_view(request):
    file_name = request.GET.get("file_name").split(".")[0] + ".json"
    path = dymanic_path("static", file_name)

    if os.path.exists(path) and os.path.isfile(path):
        with open(path, "rb") as json_file:
            json_data = json_file.read()
            response = HttpResponse(json_data, content_type="application/json")
            response["Content-Disposition"] = (
                f'attachment; filename="{os.path.basename(path)}"'
            )
            return response
    else:
        return HttpResponse("File not found", status=404)
