from django.urls import reverse
from django.db import models
from django.db.models.lookups import IsNull
from django.conf import settings

from pathlib import Path

from django.utils.crypto import get_random_string


def get_array_no_null_element_constraint(*, array_field, **kwargs):
    return models.CheckConstraint(
        # We use the PostgreSQL function "array_position" which
        # returns the index of the first occurrence of a value
        # in the given array. If the value doesn't exist, it
        # returns NULL.
        check = IsNull(
            lhs=models.Func(models.F(array_field),
                            models.Value(None),  # NULL
                            function='array_position'),
            rhs=True
        ),
        **kwargs
    )


class GameInfoQuerySet(models.QuerySet):
    def from_slug_if_visible(self, slug):
        return self.filter(slug=slug, is_visible=True).first()


# Once we create a new game, we must also make a database
# record for it through this model.
class GameInfo(models.Model):
    class ConclusionSystems(models.TextChoices):
        VICTORY_DRAW = 'VD', 'Victory or Draw'
        RANK_BASED = 'RB', 'Rank-based'
    
    name = models.CharField('name of the game directory', max_length=50, unique=True)
    title = models.CharField('display name of the game', max_length=50, unique=True)
    short_description = models.CharField(max_length=300)

    conclusion_system = models.CharField(max_length=2, choices=ConclusionSystems)
    
    has_scores = models.BooleanField()
    
    min_players = models.IntegerField()
    max_players = models.IntegerField()
    
    is_visible = models.BooleanField(default=True)
    
    documentation = models.TextField()
    
    slug = models.SlugField(unique=True, max_length=50)
    
    def get_absolute_url(self):
        return reverse('game_details', kwargs={'slug': self.slug})
    
    
    # TODO: there should be a field, specifying all the custom settings
    # that can be specified for a game with their type. For example, one
    # setting might be a choice between fixed items, or it might be an
    # integer in a certain range, or a string or some maximum length. We
    # can also specify the default for each setting key.
    
    def __str__(self):
        return self.title
    
    objects = models.Manager.from_queryset(GameInfoQuerySet)()


class GameTemplate(models.Model):
    def get_template_upload_path(self, filename):
        return Path(settings.TEMPLATE_CODES_DIR, self.game.name, filename)
            
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['game', 'title'],
                                    name='game_template_unique_game_title'),
        ]
    
    game = models.ForeignKey(GameInfo, on_delete=models.CASCADE)

    file = models.FileField(upload_to=get_template_upload_path)
    title = models.CharField(max_length=60)
    description = models.CharField(max_length=120)
    
    def __str__(self):       
        return f'{self.game.title} : {self.title}'
    


class GameCodePreset(models.Model):
    def get_code_upload_path(self, _):
        return settings.PRESET_CODES_DIR / f'{get_random_string(length=32)}.py'
    
    game_info = models.ForeignKey(GameInfo, on_delete=models.CASCADE)
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # For each game, this shows the index of the preset from 0
    # to whatever maximum it is.
    game_preset_index = models.SmallIntegerField()
    
    title = models.CharField(max_length=50)
    code_file = models.FileField(upload_to=get_code_upload_path)
    
    created_at = models.DateTimeField(auto_now_add=True)


class GameResult(models.Model):
    fight = models.OneToOneField('fights.Fight', on_delete=models.CASCADE, related_name='result')
    
    # This is mostly meant to be containing small strings. If later
    # we need more elaborate explanations, we can also use this as
    # a JSON storage (and possibly increase the max length).
    explanation = models.CharField(max_length=100, blank=True)
    
    
    # FIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # # Give a human-readable explanation to be displayed to the users. ################# doc string #########################33
    # def get_explanation(self):
    #     """must be overriden by each game's GameResult class."""
    #     return NotImplementedError
    
    
    # It's JSON, but since we don't really make any db-related uses
    # out of it, we rather keep it as a TextField.
    data = models.TextField()
    
    # def __str__(self):       
    #     return f'{self.fight.game.title}'
    
    
