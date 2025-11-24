# -*- coding: utf-8 -*-
from odoo import models, fields, api
import requests

class BibliotecaAutor(models.Model):
    _name = 'biblioteca.autor'
    _description = 'Registro de autores'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)
    nacionalidad = fields.Char(string='Nacionalidad')
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento')
    biografia = fields.Text(string='Biografía')

    @api.model
    def rellenar_desde_openlibrary(self, autor_name):
        """Obtiene información de un autor desde Open Library"""
        url = f"https://openlibrary.org/search/authors.json?q={autor_name}"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if data['numFound'] > 0:
                autor_data = data['docs'][0]
                return {
                    'name': autor_data.get('name', autor_name),
                    'nacionalidad': autor_data.get('top_work', ''),
                    'fecha_nacimiento': autor_data.get('birth_date', None),
                    'biografia': autor_data.get('bio', ''),
                }
        return {}

    def action_rellenar_openlibrary(self):
        """Botón que rellena el registro desde Open Library"""
        for record in self:
            info = self.rellenar_desde_openlibrary(record.name)
            record.update(info)
