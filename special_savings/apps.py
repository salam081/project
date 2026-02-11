from django.apps import AppConfig


class SpecialSavingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'special_savings'
    

    def ready(self):
        import special_savings.signals
    
