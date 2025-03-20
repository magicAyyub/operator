from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
import numpy as np

class PhoneOperatorAnalyzer:
    """
    Classe pour analyser les numéros de téléphone et leurs opérateurs associés.
    """
    
    def __init__(self, sample_path: Union[str, Path], operator_path: Union[str, Path]):
        """
        Initialise l'analyseur avec les chemins des fichiers de données.
        
        Args:
            sample_path: Chemin vers le fichier des données utilisateurs
            operator_path: Chemin vers le fichier des opérateurs
        """
        self.sample_path = sample_path
        self.operator_path = operator_path
        self.df: Optional[pd.DataFrame] = None
        self.df_operateur_fr: Optional[pd.DataFrame] = None
        self.df_numeros_fr: Optional[pd.DataFrame] = None
        self.df_numeros_etrangers: Optional[pd.DataFrame] = None
        
    def load_data(self) -> None:
        """Charge les données depuis les fichiers CSV."""
        # Chargement du fichier principal
        self.df = pd.read_csv(
            self.sample_path,
            dtype={
                'TELEPHONE': str,
                'ID_CCU': str,
                'INDICATIF': str,
                'COGPAYS': str
            },
            low_memory=False
        )
        
        # Chargement du fichier des opérateurs
        self.df_operateur_fr = pd.read_csv(
            self.operator_path,
            encoding='ISO-8859-1',
            sep=';'
        )
        
        self._clean_phone_numbers()
        self._prepare_operator_data()
        
    def _clean_phone_numbers(self) -> None:
        """Nettoie les numéros de téléphone."""
        if self.df is not None:
            self.df['TELEPHONE'] = (self.df['TELEPHONE']
                                  .str.replace('+', '')
                                  .str.replace('.0', ''))
            
    def _prepare_operator_data(self) -> None:
        """Prépare les données des opérateurs."""
        if self.df_operateur_fr is not None:
            self.df_operateur_fr = (
                self.df_operateur_fr
                .drop(columns=["Tranche_Debut", "Tranche_Fin", "Date_Attribution"])
                .rename(columns={
                    "EZABPQM": "Prefixe",
                    "Mnémo": "Operateur"
                })
            )
            self.df_operateur_fr['Prefixe'] = self.df_operateur_fr['Prefixe'].astype(str)
            
    def process_french_numbers(self) -> None:
        """Traite les numéros français et étrangers séparément."""
        if self.df is not None:
            # Séparation des numéros français et étrangers
            mask_fr = self.df["TELEPHONE"].str[:2] == "33"
            self.df_numeros_fr = self.df[mask_fr].copy()
            self.df_numeros_etrangers = self.df[~mask_fr].copy()
            
            # Traitement des numéros français
            if not self.df_numeros_fr.empty:
                self.df_numeros_fr['TELEPHONE'] = (
                    self.df_numeros_fr['TELEPHONE']
                    .str.replace(r'^33', '', regex=True)
                )
                self.df_numeros_fr["Longueur_numero_telephone"] = (
                    self.df_numeros_fr["TELEPHONE"].str.len()
                )
                self._create_prefix_columns()
                
    def _create_prefix_columns(self) -> None:
        """Crée les colonnes de préfixes de différentes longueurs."""
        if self.df_numeros_fr is not None:
            for i in range(3, 8):
                self.df_numeros_fr[f'Prefixe_{i}'] = (
                    self.df_numeros_fr['TELEPHONE'].str[:i]
                )
                
    def match_operators(self) -> pd.DataFrame:
        """
        Fait correspondre les numéros avec leurs opérateurs.
        
        Returns:
            DataFrame avec les correspondances numéros-opérateurs
        """
        results = []
        
        if self.df_numeros_fr is not None and self.df_operateur_fr is not None:
            for i in range(3, 8):
                df_operateur_length = self.df_operateur_fr[
                    self.df_operateur_fr["Prefixe"].str.len() == i
                ]
                
                if not df_operateur_length.empty:
                    result = self.df_numeros_fr.merge(
                        df_operateur_length,
                        left_on=f'Prefixe_{i}',
                        right_on='Prefixe',
                        how='inner'
                    )
                    results.append(result)
        
        if results:
            return pd.concat(results, axis=0)
        return pd.DataFrame()
    
    def get_final_dataframe(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Sélectionne les colonnes finales et supprime les doublons.
        
        Args:
            merged_df: DataFrame avec les correspondances
            
        Returns:
            DataFrame final nettoyé
        """
        colonnes_finales = [
            'FIRST_NAME', 'BIRTH_NAME', 'MIDDLE_NAME', 'LAST_NAME', 'SEX',
            'BIRTH_DATE', 'COGVILLE', 'COGPAYS', 'BIRTH_CITY', 'BIRTH_COUNTRY',
            'EMAIL', 'CREATED_DATE', 'UUID', 'ID_CCU', 'SUBSCRIPTION_CHANNEL',
            'VERIFICATION_MODE', 'VERIFICATION_DATE', 'USER_STATUS', '2FA_STATUS',
            'TELEPHONE', 'INDICATIF', 'DATE_MODF_TEL', 'Numero Pi', 'EXPIRATION',
            'EMISSION', 'TYPE', 'Longueur_numero_telephone', 'Prefixe',
            'Operateur', 'Territoire'
        ]
        
        return merged_df[colonnes_finales].drop_duplicates()
    
    def analyze(self) -> Tuple[pd.DataFrame, Dict]:
        """
        Effectue l'analyse complète et retourne les résultats et statistiques.
        
        Returns:
            Tuple contenant le DataFrame final et les statistiques
        """
        self.load_data()
        self.process_french_numbers()
        
        merged_df = self.match_operators()
        final_df = self.get_final_dataframe(merged_df)
        
        stats = {
            'total_numbers': len(self.df) if self.df is not None else 0,
            'french_numbers': len(self.df_numeros_fr) if self.df_numeros_fr is not None else 0,
            'foreign_numbers': len(self.df_numeros_etrangers) if self.df_numeros_etrangers is not None else 0,
            'matched_operators': len(final_df),
            'operator_distribution': final_df['Operateur'].value_counts().to_dict()
        }
        
        return final_df, stats

# Exemple d'utilisation de la classe
"""
analyzer = PhoneOperatorAnalyzer('sample_data.csv', 'operators.csv')
final_df, stats = analyzer.analyze()
print(final_df.head())"""