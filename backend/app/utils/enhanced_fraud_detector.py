from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
import pandas as pd
import numpy as np
from collections import Counter
import re
import json
from .phone_operator import PhoneOperatorAnalyzer
from app.config import Config 

def convert_to_serializable(obj: Any) -> Any:
    """
    Convertit les types numpy et pandas en types Python standards pour la sérialisation JSON.
    
    Args:
        obj: L'objet à convertir
        
    Returns:
        L'objet converti en type serializable
    """
    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return obj.to_dict()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    return obj

class EnhancedFraudDetector(PhoneOperatorAnalyzer):
    """
    Extension du PhoneOperatorAnalyzer avec des fonctionnalités de détection de fraude.
    Hérite des fonctionnalités d'analyse d'opérateurs et ajoute la détection de comportements suspects.
    """
    
    def __init__(self, sample_path: Union[str,Path], operator_path: Union[str,Path]):
        super().__init__(sample_path, operator_path)
        self.disposable_domains = [
            'tempmail', 'temp-mail', 'tmpmail', 'temporary', 'throwaway',
            'yopmail', 'mailinator', '10minutemail', 'guerrillamail'
        ]
        self.suspicious_patterns = {}
        
    def analyze_phone_patterns(self, merged_df: pd.DataFrame) -> Dict:
        """
        Analyse approfondie des patterns téléphoniques suspects.
        
        Cette analyse inclut :
        - La détection des préfixes rares
        - L'identification des numéros séquentiels
        - Le repérage des réutilisations de numéros
        - La vérification de la cohérence géographique entre le territoire de l'opérateur
          et les pays déclarés/de naissance
        """
        phone_patterns = {
            'sequential_numbers': [],
            'reused_numbers': {},
            'suspicious_prefixes': [],
            'geographic_mismatches': []
        }
        
        # Analyse des préfixes rares (moins de 1% des occurrences)
        prefix_counts = merged_df['Prefixe'].value_counts()
        rare_threshold = len(merged_df) * 0.01
        suspicious_prefixes = prefix_counts[prefix_counts < rare_threshold].index.tolist()
        phone_patterns['suspicious_prefixes'] = suspicious_prefixes
        
        # Détection des numéros séquentiels
        phone_numbers = merged_df['TELEPHONE'].dropna().sort_values()
        phone_numbers = pd.to_numeric(phone_numbers, errors='coerce')
        phone_numbers = phone_numbers.dropna()
        
        for i in range(len(phone_numbers) - 1):
            if phone_numbers.iloc[i+1] - phone_numbers.iloc[i] == 1:
                phone_patterns['sequential_numbers'].append(
                    str(int(phone_numbers.iloc[i]))
                )
        
        # Analyse des réutilisations de numéros
        number_counts = merged_df['TELEPHONE'].value_counts()
        phone_patterns['reused_numbers'] = {
            str(k): int(v) for k, v in number_counts[number_counts > 1].items()
        }
        
        # Vérification de la cohérence géographique
        for _, row in merged_df.iterrows():
            if pd.isna(row['TELEPHONE']) or pd.isna(row['Territoire']):
                continue
                
            telephone = str(row['TELEPHONE'])
            territoire_operateur = str(row['Territoire'])
            birth_country = str(row['BIRTH_COUNTRY'])
            declared_country = str(row['COGPAYS'])
            
            # On vérifie si le territoire de l'opérateur correspond aux pays déclarés
            if territoire_operateur != 'nan' and birth_country != 'nan' and declared_country != 'nan':
                if territoire_operateur not in [birth_country, declared_country]:
                    mismatch_info = {
                        'telephone': telephone,
                        'operateur': str(row['Operateur']),
                        'territoire_operateur': territoire_operateur,
                        'pays_naissance': birth_country,
                        'pays_declare': declared_country
                    }
        
        return phone_patterns
    
    def analyze_email_patterns(self) -> Dict:
        """
        Analyse des patterns d'emails suspects.
        """
        if self.df is None:
            return {}
            
        email_patterns = {
            'temp_domains': [],
            'suspicious_usernames': [],
            'domain_distribution': {},
            'malformed_emails': []
        }
        
        emails = self.df['EMAIL'].dropna()
        
        for email in emails:
            if not isinstance(email, str):
                continue
                
            # Validation basique du format
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                email_patterns['malformed_emails'].append(str(email))
                continue
            
            # Analyse du domaine
            domain = email.split('@')[1].lower()
            email_patterns['domain_distribution'][domain] = \
                email_patterns['domain_distribution'].get(domain, 0) + 1
            
            # Détection des domaines temporaires
            if any(temp in domain for temp in self.disposable_domains):
                email_patterns['temp_domains'].append(str(email))
            
            # Analyse du nom d'utilisateur
            username = email.split('@')[0]
            if len(username) > 20 or username.isdigit() or \
               re.match(r'.*\d{4,}.*', username):
                email_patterns['suspicious_usernames'].append(str(email))
        
        # Conversion des compteurs en entiers standards
        email_patterns['domain_distribution'] = {
            k: int(v) for k, v in email_patterns['domain_distribution'].items()
        }
        
        return email_patterns
    
    def calculate_risk_scores(self, phone_patterns: Dict, email_patterns: Dict) -> pd.DataFrame:
        """
        Calcule un score de risque pour chaque compte basé sur les patterns détectés.
        """
        if self.df is None:
            return pd.DataFrame()
            
        risk_scores = pd.DataFrame()
        risk_scores['ID_CCU'] = self.df['ID_CCU']
        
        # Initialisation des scores
        risk_scores['phone_risk'] = 0
        risk_scores['email_risk'] = 0
        
        # Score basé sur le téléphone
        reused_numbers = set(phone_patterns['reused_numbers'].keys())
        risk_scores.loc[self.df['TELEPHONE'].isin(reused_numbers), 'phone_risk'] += 2
        
        sequential_numbers = set(phone_patterns['sequential_numbers'])
        risk_scores.loc[self.df['TELEPHONE'].isin(sequential_numbers), 'phone_risk'] += 3
        
        # Score basé sur l'email
        temp_emails = set(email_patterns['temp_domains'])
        risk_scores.loc[self.df['EMAIL'].isin(temp_emails), 'email_risk'] += 3
        
        suspicious_emails = set(email_patterns['suspicious_usernames'])
        risk_scores.loc[self.df['EMAIL'].isin(suspicious_emails), 'email_risk'] += 2
        
        # Score total
        risk_scores['total_risk'] = risk_scores['phone_risk'] + risk_scores['email_risk']
        
        return risk_scores
    
    def generate_comprehensive_report(self) -> Tuple[Dict, pd.DataFrame, pd.DataFrame]:
        """
        Génère un rapport complet d'analyse avec tous les indicateurs.
        """
        # Utilisation des fonctionnalités héritées
        self.load_data()
        self.process_french_numbers()
        merged_df = self.match_operators()
        final_df = self.get_final_dataframe(merged_df)
        
        # Nouvelles analyses
        phone_patterns = self.analyze_phone_patterns(final_df)
        email_patterns = self.analyze_email_patterns()
        risk_scores = self.calculate_risk_scores(phone_patterns, email_patterns)
        
        # Création du rapport avec conversion des types
        report = {
            'summary': {
                'total_accounts': int(len(self.df)) if self.df is not None else 0,
                'accounts_with_phone': int(len(final_df)),
                'accounts_with_email': int(self.df['EMAIL'].notna().sum()) if self.df is not None else 0,
                'high_risk_accounts': int(len(risk_scores[risk_scores['total_risk'] > 3]))
            },
            'phone_analysis': convert_to_serializable(phone_patterns),
            'email_analysis': convert_to_serializable(email_patterns),
            'risk_distribution': convert_to_serializable(
                risk_scores['total_risk'].value_counts().to_dict()
            )
        }
        
        return report, risk_scores, final_df

def main():
    # Initialisation avec les deux fichiers nécessaires
    detector = EnhancedFraudDetector(Config.DETECTOR_FIRST_INPUT, Config.DETECTOR_SECOND_OUTPUT)
    
    try:
        # Génération du rapport complet
        report, risk_scores, final_df = detector.generate_comprehensive_report()
        
        # Sauvegarde des résultats
        with open('rapport_fraude.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=4)
            
        # Sauvegarde des scores de risque
        risk_scores.to_csv('scores_risque.csv', index=False)
        
        # Sauvegarde du DataFrame final enrichi
        final_df.to_csv('donnees_enrichies.csv', index=False)
        
        print("\nAnalyse terminée avec succès. Résultats sauvegardés dans:")
        print("- rapport_fraude.json: Rapport complet d'analyse")
        print("- scores_risque.csv: Scores de risque par compte")
        print("- donnees_enrichies.csv: Données enrichies avec analyses")
        
    except Exception as e:
        print(f"\nUne erreur s'est produite lors de l'analyse: {str(e)}")
        raise
