import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# CatheterRegistration
#

class CatheterRegistration(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Catheter Registration" # TODO make this more human readable by adding spaces
    self.parent.categories = ["IGT"]
    self.parent.dependencies = ["Segmentations", "ModelRegistration"]
    self.parent.contributors = ["Csaba Pinter (Queen's University)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module registers a set of segmented catheters to a set of reconstructed catheters.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
""" # replace with organization, grant and thanks.

#
# CatheterRegistrationWidget
#

class CatheterRegistrationWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/CatheterRegistration.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    self.ui.MRMLNodeComboBox_SegmentedCatheters.setMRMLScene(slicer.mrmlScene)
    self.ui.SubjectHierarchyComboBox_ReconstructedCatheters.setMRMLScene(slicer.mrmlScene)
    self.ui.SubjectHierarchyComboBox_ReconstructedCatheters.setNodeTypes(["vtkMRMLModelNode"])
    self.ui.MRMLNodeComboBox_DistanceHistogramTable.setMRMLScene(slicer.mrmlScene)

    # connections
    self.ui.registerButton.connect('clicked(bool)', self.onRegisterButton)
    self.ui.MRMLNodeComboBox_SegmentedCatheters.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.ui.SubjectHierarchyComboBox_ReconstructedCatheters.connect("currentItemChanged(vtkIdType)", self.onSelect)
    self.ui.MRMLNodeComboBox_DistanceHistogramTable.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def cleanup(self):
    pass

  def onSelect(self):
    segmentedCathetersSelected = self.ui.MRMLNodeComboBox_SegmentedCatheters.currentNode()

    pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
    folderPlugin = pluginHandler.pluginByName('Folder')
    reconstructedCathetersValid = folderPlugin.canOwnSubjectHierarchyItem(self.ui.SubjectHierarchyComboBox_ReconstructedCatheters.currentItem())

    distanceHistogramTableSelected = self.ui.MRMLNodeComboBox_DistanceHistogramTable.currentNode()

    self.ui.registerButton.enabled = segmentedCathetersSelected and reconstructedCathetersValid and distanceHistogramTableSelected

  def onRegisterButton(self):
    logic = CatheterRegistrationLogic(self)
    logic.run(self.ui.MRMLNodeComboBox_SegmentedCatheters.currentNode(), self.ui.SubjectHierarchyComboBox_ReconstructedCatheters.currentItem(), self.ui.MRMLNodeComboBox_DistanceHistogramTable.currentNode())
    self.ui.label_RegistrationError.text = str(logic.registrationError)

#
# CatheterRegistrationLogic
#

class CatheterRegistrationLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModuleLogic.__init__(self, parent)

    self.registrationError = None

  def run(self, cathetersSegmentationNode, reconstructedCathetersFolderItemId, distanceHistogramTableNode):
    """
    Run the actual algorithm
    """

    if not cathetersSegmentationNode or reconstructedCathetersFolderItemId == 0:
      slicer.util.errorDisplay('Invalid catheter segmentation or reconstructed catheter folder selection')
      return False

    #
    # Prepare registration input model nodes
    #

    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

    # Get reconstructed model nodes
    children = vtk.vtkIdList()
    reconstructedCatheterModels = []
    shNode.GetItemChildren(reconstructedCathetersFolderItemId, children)
    for i in range(children.GetNumberOfIds()):
      child = children.GetId(i)
      childDataNode = shNode.GetItemDataNode(child)
      if childDataNode and childDataNode.IsA("vtkMRMLModelNode"):
        reconstructedCatheterModels.append(childDataNode)
    logging.info('Reconstructed catheter model nodes: ' + str(len(reconstructedCatheterModels)))

    # Create appended reconstructed model node
    reconstructedCathetersModel = None
    try:
      reconstructedCathetersModel = slicer.util.getNode('Reconstructed Catheter Models')
    except slicer.util.MRMLNodeNotFoundException:
      reconstructedCathetersModel = slicer.vtkMRMLModelNode()
      slicer.mrmlScene.AddNode(reconstructedCathetersModel)
      reconstructedCathetersModel.CreateDefaultDisplayNodes()
      reconstructedCathetersModel.SetName('Reconstructed Catheter Models')

    # Append reconstructed model nodes
    append = vtk.vtkAppendPolyData()
    for modelNode in reconstructedCatheterModels:
      append.AddInputData(modelNode.GetPolyData())
    append.Update()
    reconstructedCathetersPolyData = vtk.vtkPolyData()
    reconstructedCathetersPolyData.DeepCopy(append.GetOutput())
    reconstructedCathetersModel.SetAndObservePolyData(reconstructedCathetersPolyData)

    # Check if number of models and segments match
    segmentation = cathetersSegmentationNode.GetSegmentation()
    logging.info('Segmented catheters: ' + str(segmentation.GetNumberOfSegments()))
    if len(reconstructedCatheterModels) != segmentation.GetNumberOfSegments():
      slicer.util.errorDisplay('Different number of catheters in selected segmentation and reconstructed catheter folder')
      return False

    # Make sure there is closed surface in the segmentation
    if not cathetersSegmentationNode.CreateClosedSurfaceRepresentation():
      slicer.util.errorDisplay('Failed to access closed surface representation in catheter segmentation')
      return False

    # Create appended segmented model node
    segmentedCathetersModel = None
    try:
      segmentedCathetersModel = slicer.util.getNode('Segmented Catheter Models')
    except slicer.util.MRMLNodeNotFoundException:
      segmentedCathetersModel = slicer.vtkMRMLModelNode()
      slicer.mrmlScene.AddNode(segmentedCathetersModel)
      segmentedCathetersModel.CreateDefaultDisplayNodes()
      segmentedCathetersModel.SetName('Segmented Catheter Models')

    # Append segmented catheters
    segmentIDs = vtk.vtkStringArray()
    segmentation.GetSegmentIDs(segmentIDs)
    append.RemoveAllInputs()
    for i in range(segmentIDs.GetNumberOfValues()):
      catheterPolyData = cathetersSegmentationNode.GetClosedSurfaceRepresentation(segmentIDs.GetValue(i))
      append.AddInputData(catheterPolyData)
    append.Update()
    segmentedCathetersModel.SetAndObservePolyData(append.GetOutput())

    #
    # Register catheters
    #

    # Create output transform
    reconstructedToSegmentedCathetersTransform = slicer.vtkMRMLLinearTransformNode()
    slicer.mrmlScene.AddNode(reconstructedToSegmentedCathetersTransform)
    reconstructedToSegmentedCathetersTransform.SetName(slicer.mrmlScene.GenerateUniqueName('ReconstructedToSegmentedCathetersTransform'))

    # Run registration
    import ModelRegistration
    logic = ModelRegistration.ModelRegistrationLogic()
    logic.run(reconstructedCathetersModel, segmentedCathetersModel, reconstructedToSegmentedCathetersTransform)

    reconstructedCathetersModel.SetAndObserveTransformNodeID(reconstructedToSegmentedCathetersTransform.GetID())

    self.registrationError = logic.ComputeMeanDistance(reconstructedCathetersModel, segmentedCathetersModel, reconstructedToSegmentedCathetersTransform)
    logging.info('Registration error: ' + str(self.registrationError))

    if distanceHistogramTableNode:
      # Create transformed poly data for comparison
      transformPoly = vtk.vtkTransformPolyDataFilter()
      transformPoly.SetInputData(reconstructedCathetersModel.GetPolyData())
      transformPoly.SetTransform(reconstructedToSegmentedCathetersTransform.GetTransformToParent())
      transformPoly.Update()

      # Calculate distance histogram
      polyDist = slicer.vtkPolyDataDistanceHistogramFilter()
      polyDist.SetInputReferencePolyData(segmentedCathetersModel.GetPolyData())
      polyDist.SetInputComparePolyData(transformPoly.GetOutput())
      polyDist.Update()

      distanceHistogramTableNode.SetAndObserveTable(polyDist.GetOutputHistogram())
      doubleType = slicer.vtkMRMLTableNode.GetValueTypeFromString('double')
      distanceHistogramTableNode.SetColumnType('Frequencies', doubleType)
      logging.info('Average Hausdorff distance: ' + str(polyDist.GetAverageHausdorffDistance()))
      logging.info('Maximum Hausdorff distance: ' + str(polyDist.GetMaximumHausdorffDistance()))

    logging.info('Catheter registration completed')

    return True


class CatheterRegistrationTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_CatheterRegistration1()

  def test_CatheterRegistration1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import SampleData
    SampleData.downloadFromURL(
      nodeNames='FA',
      fileNames='FA.nrrd',
      uris='http://slicer.kitware.com/midas3/download?items=5767',
      checksums='SHA256:12d17fba4f2e1f1a843f0757366f28c3f3e1a8bb38836f0de2a32bb1cd476560')
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = CatheterRegistrationLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
