server {
    listen 80;
    server_name avtomat.ukudarov.pro;

    client_max_body_size 50M;

    location /static/ {
        alias /home/ubuntu/automat_backend/srm_backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /home/ubuntu/automat_backend/srm_backend/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
