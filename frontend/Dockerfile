FROM nginx:alpine

# Copy all frontend static assets in one shot — keeps the image in sync as
# new modules (heatmap.js, interactive.js, …) get added.
COPY *.html *.css *.js /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
