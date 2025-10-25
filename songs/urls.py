from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # 🌸 Welcome
    path('welcome/', views.welcome, name='welcome'),
    
    # 🎵 Song CRUD
    path('', views.song_list, name='song_list'),
    path('add/', views.song_add, name='song_add'),
    path('view/<int:pk>/', views.song_view, name='song_view'),
    path('edit/<int:pk>/', views.song_edit, name='song_edit'),
    path('delete/<int:pk>/', views.song_delete, name='song_delete'),
    path('add-language/<int:pk>/', views.song_add_language, name='song_add_language'),
    path("check-contact/", views.check_contact, name="check_contact"),

    
    # 💛 Song Actions
    path('toggle-favorite/<int:pk>/', views.song_toggle_favorite, name='song_toggle_favorite'),
    
    # 🎧 Downloads
    path('download/<int:pk>/', views.song_download, name='song_download'),
    path('download-pdf/<int:pk>/', views.song_download_pdf, name='song_download_pdf'),
    path('bulk-download/', views.bulk_download, name='bulk_download'),

    # 👥 Authentication
    path('accounts/login/', views.user_login, name='login'),
    path('accounts/logout/', views.user_logout, name='logout'),
    path('accounts/register/', views.user_register, name='register'),

    # 📱 Custom OTP Password Reset (Phone-based)
    path('password-reset/phone/', views.reset_with_phone, name='reset_with_phone'),
    path('password-reset/otp/', views.verify_otp, name='verify_otp'),
    path('password-reset/new/', views.set_new_password, name='set_new_password'),
    path('password-reset/resend/', views.resend_otp, name='resend_otp'),


    # 📧 Optional Django built-in Email Reset (kept for fallback)
    path('accounts/password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='songs/password_reset.html'
         ),
         name='password_reset'),

    path('accounts/password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='songs/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='songs/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),

    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='songs/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # 🔒 Access Control
    path('request-access/<int:pk>/', views.request_song_access, name='request_song_access'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('admin/access-requests/', views.admin_access_requests, name='admin_access_requests'),
    path('admin/grant-access/<int:pk>/', views.admin_grant_access, name='admin_grant_access'),
    path('admin/deny-access/<int:pk>/', views.admin_deny_access, name='admin_deny_access'),
    path('admin/manage-access/', views.admin_manage_access, name='admin_manage_access'),
    path("create-admin/", views.create_admin, name="create_admin"),
    
    # 🧑‍💼 Custom Admin Dashboard
    path('admin/users/', views.admin_users_dashboard, name='admin_users_dashboard'),
    path('admin/user/<int:user_id>/detail/', views.admin_user_detail, name='admin_user_detail'),
    path('admin/user/<int:user_id>/song-access/', views.admin_user_song_access, name='admin_user_song_access'),
    path('admin/user/<int:user_id>/revoke-all/', views.admin_revoke_all_access, name='admin_revoke_all_access'),
    
    # 🔔 Push Notifications
    path('admin/send-notification/', views.admin_send_notification, name='admin_send_notification'),
    
    # ⚙️ Admin Settings
    path('admin/settings/', views.admin_settings, name='admin_settings'),
#     path("admin/category/add/", views.add_category, name="add_category"),
#     path("admin/category/update/", views.update_category, name="update_category"),
#     path("admin/category/delete/", views.delete_category, name="delete_category"),
    
    # 🕉️ Astotharam
    path('astotharam/', views.astotharam_list, name='astotharam_list'),
    path('astotharam/add/', views.astotharam_add, name='astotharam_add'),
    path('astotharam/<int:pk>/', views.astotharam_view, name='astotharam_view'),
    path('astotharam/<int:pk>/edit/', views.astotharam_edit, name='astotharam_edit'),
    path('astotharam/<int:pk>/delete/', views.astotharam_delete, name='astotharam_delete'),
    
    # 🪔 Saranaghosha
    path('saranaghosha/', views.saranaghosha_list, name='saranaghosha_list'),
    path('saranaghosha/add/', views.saranaghosha_add, name='saranaghosha_add'),
    path('saranaghosha/<int:pk>/', views.saranaghosha_view, name='saranaghosha_view'),
    path('saranaghosha/<int:pk>/edit/', views.saranaghosha_edit, name='saranaghosha_edit'),
    path('saranaghosha/<int:pk>/delete/', views.saranaghosha_delete, name='saranaghosha_delete'),
    
    # 📴 Offline Page
    path('offline/', views.offline_page, name='offline_page'),
]
