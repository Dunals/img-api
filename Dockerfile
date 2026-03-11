FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright වලට ඕනේ කරන බ්‍රව්සර් සහ අනිත් කෑලි ඉන්ස්ටෝල් කිරීම
RUN playwright install chromium
RUN playwright install-deps

COPY . .

EXPOSE 10000

CMD ["python", "main.py"]