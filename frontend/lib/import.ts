"use server"

export async function importData(formData) {
  try {
    // For the mapping file, we can upload it directly as it's typically smaller
    const mappingFile = formData.get("mappingFile")

    // Get all data files
    const dataFiles = formData.getAll("dataFiles")

    // Track overall progress and results
    const results = {
      success: true,
      processedFiles: [],
      errors: [],
      rowsImported: 0,
    }

    // Process each data file using chunked upload
    for (const file of dataFiles) {
      try {
        // Upload the file in chunks
        const fileId = await uploadFileInChunks(file)

        // Once the file is uploaded, tell the server to process it
        const processResponse = await fetch("/api/process_chunked_file", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            fileId,
            fileName: file.name,
            mappingFileName: mappingFile.name,
          }),
        })

        if (!processResponse.ok) {
          const errorData = await processResponse.json()
          throw new Error(errorData.error || `Failed to process file ${file.name}`)
        }

        const processResult = await processResponse.json()
        results.processedFiles.push(processResult.outputFile)
        results.rowsImported += 1
      } catch (error) {
        results.errors.push(`Error processing ${file.name}: ${error.message}`)
        results.success = false
      }
    }

    return results
  } catch (error) {
    console.error("Import error:", error)
    throw error
  }
}

// Function to upload a file in chunks
async function uploadFileInChunks(file, chunkSize = 1024 * 1024) {
  // 1MB chunks
  const fileId = generateUniqueId()
  const totalChunks = Math.ceil(file.size / chunkSize)

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * chunkSize
    const end = Math.min(start + chunkSize, file.size)
    const chunk = file.slice(start, end)

    const chunkFormData = new FormData()
    chunkFormData.append("fileId", fileId)
    chunkFormData.append("fileName", file.name)
    chunkFormData.append("chunkIndex", chunkIndex.toString())
    chunkFormData.append("totalChunks", totalChunks.toString())
    chunkFormData.append("chunk", chunk)

    const response = await fetch("/api/upload_chunk", {
      method: "POST",
      body: chunkFormData,
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || "Failed to upload chunk")
    }
  }

  return fileId
}

// Generate a unique ID for the file upload
function generateUniqueId() {
  return `file_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
}