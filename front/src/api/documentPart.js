import axios from "axios";

// retrieve single element (document part)
export const retrieveDocumentPart = async (documentId, partId) =>
    await axios.get(`/documents/${documentId}/parts/${partId}/`);

// retrieve document part by order (page number/position)
export const retrieveDocumentPartByOrder = async (documentId, order) =>
    await axios.get(`/documents/${documentId}/parts/byorder/?order=${order}`);

// every element of a document with its label, filename and thumbnail (not paginated)
export const retrieveDocumentPartsNavigation = async (documentId) =>
    await axios.get(`/documents/${documentId}/parts/navigation/`);

// set the editorial status of one or several elements of a document
export const setPartsEditorialStatus = async (documentId, partIds, status) =>
    await axios.post(`/documents/${documentId}/parts/set_status/`, {
        parts: partIds,
        status,
    });

// set the TEI work ("work") or work URI ("work_uri") of one or several elements of a document;
// an empty value removes it
export const setPartsMetadata = async (documentId, partIds, key, value) =>
    await axios.post(`/documents/${documentId}/parts/set_metadata/`, {
        parts: partIds,
        key,
        value,
    });

// name one or several elements of a document by folio, in their order: 1r, 1v, 2r, 2v... from start
export const numberFolios = async (documentId, partIds, start) =>
    await axios.post(`/documents/${documentId}/parts/number_folios/`, {
        parts: partIds,
        start,
    });

export const updatePart = async (documentId, partId, data) =>
    await axios.patch(`/documents/${documentId}/parts/${partId}/`, data);

export const retrievePartMetadata = async (documentId, partId) =>
    await axios.get(`/documents/${documentId}/parts/${partId}/metadata/`);

export const retrievePartMetadatum = async (documentId, partId, metadataId) =>
    await axios.get(
        `/documents/${documentId}/parts/${partId}/metadata/${metadataId}/`,
    );

export const createPartMetadata = async (documentId, partId, data) =>
    await axios.post(
        `/documents/${documentId}/parts/${partId}/metadata/`,
        data,
    );

export const updatePartMetadata = async (
    documentId,
    partId,
    metadataId,
    data,
) =>
    await axios.patch(
        `/documents/${documentId}/parts/${partId}/metadata/${metadataId}/`,
        data,
    );

export const deletePartMetadata = async (documentId, partId, metadataId) =>
    await axios.delete(
        `/documents/${documentId}/parts/${partId}/metadata/${metadataId}/`,
    );

export const rotateDocumentPart = async (documentId, partId, data) =>
    await axios.post(`/documents/${documentId}/parts/${partId}/rotate/`, data);

// move a single document part
export const moveDocumentPart = async ({ documentId, partId, index }) =>
    await axios.post(`/documents/${documentId}/parts/${partId}/move/`, {
        index,
    });

// move multiple document parts
export const bulkMoveParts = async ({ documentId, parts, index }) =>
    await axios.post(`/documents/${documentId}/bulk_move_parts/`, {
        parts,
        index,
    });
