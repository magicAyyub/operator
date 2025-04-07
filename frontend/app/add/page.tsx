"use client";

import React, { useState } from 'react';
import { Upload, ArrowLeft, AlertTriangle } from 'lucide-react';
import LoadDataModal from '@/components/LoadDataModal';
import ProgressIndicator from '@/components/ProgressIndicator';

const AddPage = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [error, setError] = useState('');
  const [isLoadDataModalOpen, setIsLoadDataModalOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');

  const URL = 'http://localhost:8000'


  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.txt')) {
      setSelectedFile(file);
      setError('');
    } else {
      setError('Veuillez sélectionner un fichier .txt');
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.name.endsWith('.txt')) {
      setSelectedFile(file);
      setError('');
    } else {
      setError('Veuillez sélectionner un fichier .txt');
    }
  };

  const handleFileProcess = async () => {
    if (!selectedFile) {
      setError("Veuillez sélectionner un fichier texte (.txt)");
      return;
    }

    setIsLoading(true);
    setError('');
    setProgress(0);
    setStage('Initialisation');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${URL}/api/process_file`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || data.details || 'Erreur lors du traitement du fichier');
      }

      setShowResults(true);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadCSV = async () => {
    try {
      const response = await fetch(`${URL}/api/download_csv`);
      if (!response.ok) {
        throw new Error('Erreur lors du téléchargement');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'processed_data.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-3xl">
      <h1 className="text-3xl font-bold mb-6 text-center">
        Chargement de nouvelles données
      </h1>

      <div className="bg-white shadow-md rounded-lg p-6 relative">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded">
            <div className="flex">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
                <p className="text-xs text-red-600 mt-1">
                  Si le problème persiste, veuillez vérifier l'encodage du fichier et réessayer.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="bg-white p-6 flex flex-col h-[280px] relative">
          <h2 className="text-xl font-semibold mb-4">
            Étape 1 : Téléchargement du fichier texte
          </h2>

          <div className="flex-1 flex flex-col">
            <div
              className={`
                flex-1 border-2 border-dashed rounded-lg 
                relative
                transition-colors duration-200
                ${dragActive ? 'border-black bg-gray-50' : 'border-gray-300'}
                ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-400 cursor-pointer'}
              `}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept=".txt"
                onChange={handleFileSelect}
                className="hidden"
                id="txtFile"
                disabled={isLoading}
              />
              <label 
                htmlFor="txtFile" 
                className="absolute inset-0 flex flex-col items-center justify-center cursor-pointer"
              >
                <Upload className="w-12 h-12 text-gray-400 mb-4" />
                <p className="text-center text-gray-600">
                  Cliquez pour sélectionner un fichier texte
                  <br />
                  ou glissez-déposez le ici
                </p>
                {selectedFile && (
                  <p className="mt-2 text-sm text-gray-500">
                    Fichier sélectionné : {selectedFile.name}
                  </p>
                )}
              </label>
            </div>

            <button
              onClick={handleFileProcess}
              disabled={!selectedFile || isLoading}
              className={`
                mt-4 w-full py-2 px-4 rounded-lg font-medium
                transition-colors duration-200
                ${(!selectedFile || isLoading)
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-black text-white hover:bg-gray-800'}
              `}
            >
              {isLoading ? 'Extraction en cours...' : 'Extraction'}
            </button>
          </div>
          <a
            href="/"
            className="absolute top-[-40px] left-[-40px] flex items-center justify-center w-12 h-12 bg-black text-white rounded-full hover:bg-gray-800 transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </a>
        </div>

        {isLoading && (
          <div className="absolute inset-0 bg-white bg-opacity-90 flex items-center justify-center rounded-lg">
            <div className="w-full max-w-md p-6">
              <ProgressIndicator progress={progress} stage={stage} />
            </div>
          </div>
        )}
      </div>

      {showResults && (
        <div className="bg-white shadow-md rounded-lg p-6 mt-6">
          <h2 className="text-xl font-semibold mb-4">
            Étape 2 : Téléchargement et chargement de données
          </h2>
          
          <div className="space-y-4">
            <button
              onClick={handleDownloadCSV}
              className="w-full bg-black text-white p-2 rounded-md hover:bg-gray-800 transition-colors"
            >
              Télécharger en CSV
            </button>

            <button
              onClick={() => setIsLoadDataModalOpen(true)}
              className="w-full border border-black text-black p-2 rounded-md hover:bg-gray-100 transition-colors"
            >
              Charger dans la base de données
            </button>
          </div>
        </div>
      )}

      <LoadDataModal
        isOpen={isLoadDataModalOpen}
        onClose={() => setIsLoadDataModalOpen(false)}
      />
    </div>
  );
};

export default AddPage;