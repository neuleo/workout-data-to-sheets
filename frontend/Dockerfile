FROM nginx:stable-alpine

# Kopiere die statischen Frontend-Dateien
COPY ./ /usr/share/nginx/html

# Überschreibe die Standard-Nginx-Konfiguration mit unserer eigenen
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80